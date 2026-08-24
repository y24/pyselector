from __future__ import annotations

import os
import re
import subprocess
from argparse import Namespace
from typing import Any

from pyselector.commands import common
from pyselector.commands.common import (
    _ensure_actions_allowed,
    _info_logger,
    _use_color,
)
from pyselector.model.element_info import ElementInfo
from pyselector.model.lifecycle_result import CloseResult, LaunchResult
from pyselector.output.json_output import format_close_result_json, format_launch_result_json
from pyselector.output.text_output import format_close_result, format_launch_result
from pyselector.record import capture as record_capture
from pyselector.utils.errors import ActionFailedError, ArgumentError, TargetWindowNotFoundError
from pyselector.utils.logging import info_log
from pyselector.wait import DEFAULT_POLL_INTERVAL, poll_until

#: 起動したプロセスとは別のプロセスがウィンドウを出すアプリ（calc.exe など）があるため、
#: pid の一致は当てにしない。--wait-title-re が指定されていればそちらを正とする。
DEFAULT_LAUNCH_TIMEOUT = 30


def run_launch(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    common.setup_dpi_awareness()

    plan = _launch_plan(args)
    dry_run = getattr(args, "dry_run", False)
    if not dry_run:
        # 任意の実行ファイルを起動することは、ボタンを 1 つ押すことより影響が
        # 小さいとは言えない。act と同じ関門を通す（設計 11 §3.3）。
        _ensure_actions_allowed(args)

    backend = args.backend
    inspector = common._create_inspector(backend)

    attached = False
    window: ElementInfo | None = None
    pid: int | None = None

    if getattr(args, "attach_existing", False):
        window = _find_window(inspector, plan, None)
        attached = window is not None
        if attached:
            log(f"{backend}: 既に起動しています。接続しました。")

    if window is None and not dry_run:
        # 起動前のウィンドウを控えておく。同じアプリが既に開いていると、タイトルの
        # 正規表現だけでは古いウィンドウを掴んでしまう。
        existing = _window_handles(inspector)
        log(f"{backend}: 起動します... {plan['exe']}")
        pid = _start(plan)
        window, outcome = _wait_for_window(inspector, plan, pid, args, existing)
        if window is None:
            raise TargetWindowNotFoundError(
                f"起動しましたが（pid={pid}）、{plan['timeout']}秒以内に対象ウィンドウが現れませんでした。"
                "--wait-title-re を見直すか --timeout を伸ばしてください"
            )
        log(f"{backend}: ウィンドウを見つけました。（{outcome.rounded}秒 / {outcome.attempts}回）")

    target_window = inspector.get_target_window(window) if window is not None else None
    recorded = None
    if window is not None and not dry_run:
        recorded = record_capture.record_launch(backend, plan, target_window, getattr(args, "note", None))
        if recorded is not None:
            log(f"記録しました。手順 {recorded.seq}")

    result = LaunchResult(
        backend=backend,
        exe=str(plan["exe"]),
        args=list(plan["args"]),
        window_title_re=plan["window_title_re"],
        timeout=plan["timeout"],
        dry_run=dry_run,
        attached=attached,
        pid=pid,
        window=window,
        target_window=target_window,
    )
    output = (
        format_launch_result_json(result, recorded=recorded)
        if json_output
        else format_launch_result(result, color)
    )
    print(output, end="")
    return 0


def run_close(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    common.setup_dpi_awareness()

    dry_run = getattr(args, "dry_run", False)
    forced = getattr(args, "force", False)
    if not dry_run:
        _ensure_actions_allowed(args)

    backend = args.backend
    inspector = common._create_inspector(backend)
    if args.window_handle is not None:
        window = inspector.find_window_by_handle(args.window_handle)
    else:
        window = inspector.find_window_by_title(args.window_title, getattr(args, "title_re", False))
    target_window = inspector.get_target_window(window)

    performed = False
    method = None
    if dry_run:
        log(f"{backend}: --dry-run のため閉じません。")
    elif forced:
        pid = window.process_id or target_window.process_id
        if pid is None:
            raise ActionFailedError("プロセス ID を特定できませんでした")
        log(f"{backend}: プロセスを終了します... pid={pid}")
        _terminate(pid)
        performed = True
        method = "terminate"
    else:
        log(f"{backend}: ウィンドウを閉じます...")
        method = inspector.perform_action(window, "close")
        performed = True

    recorded = None
    if performed:
        recorded = record_capture.record_close(backend, target_window, forced, getattr(args, "note", None))
        if recorded is not None:
            log(f"記録しました。手順 {recorded.seq}")

    result = CloseResult(
        backend=backend,
        performed=performed,
        dry_run=dry_run,
        forced=forced,
        method=method,
        window=window,
        target_window=target_window,
    )
    output = (
        format_close_result_json(result, recorded=recorded)
        if json_output
        else format_close_result(result, color)
    )
    print(output, end="")
    return 0


def _launch_plan(args: Namespace) -> dict[str, Any]:
    """設定と引数から、起動する内容を 1 つに決める。"""
    app = getattr(args, "app", None)
    apps = getattr(args, "apps", {}) or {}
    entry: dict[str, Any] = {}
    if app is not None:
        if app not in apps:
            known = ", ".join(sorted(apps)) or "（設定なし）"
            raise ArgumentError(f"設定に app がありません: {app}（定義済み: {known}）")
        entry = dict(apps[app])

    exe = getattr(args, "exe", None) or entry.get("exe")
    if not exe:
        raise ArgumentError("--exe か --app のどちらかで起動対象を指定してください")
    extra_args = getattr(args, "args", None)
    return {
        "exe": exe,
        "args": list(extra_args if extra_args is not None else entry.get("args", [])),
        "window_title_re": getattr(args, "wait_title_re", None) or entry.get("window_title_re"),
        "timeout": getattr(args, "timeout", None) or entry.get("timeout") or DEFAULT_LAUNCH_TIMEOUT,
    }


def _start(plan: dict[str, Any]) -> int:
    command = [str(plan["exe"]), *[str(arg) for arg in plan["args"]]]
    try:
        process = subprocess.Popen(command, close_fds=True)
    except OSError as exc:
        raise ActionFailedError(f"起動できませんでした: {command[0]}: {exc}") from exc
    return process.pid


def _wait_for_window(
    inspector: Any,
    plan: dict[str, Any],
    pid: int,
    args: Namespace,
    existing: set[int] | None = None,
):
    return poll_until(
        lambda: _find_window(inspector, plan, pid, existing),
        lambda window: window is not None,
        timeout=plan["timeout"],
        poll_interval=getattr(args, "poll_interval", DEFAULT_POLL_INTERVAL),
    )


def _window_handles(inspector: Any) -> set[int]:
    try:
        return {window.handle for window in inspector.list_windows(True) if window.handle is not None}
    except Exception:
        return set()


def _find_window(
    inspector: Any,
    plan: dict[str, Any],
    pid: int | None,
    existing: set[int] | None = None,
) -> ElementInfo | None:
    """対象の主ウィンドウを探す。

    タイトルの正規表現が指定されていればそれを正とする。指定が無いときだけ、
    起動したプロセス ID に望みを託す。calc.exe のように別プロセスがウィンドウを
    出すアプリでは pid が一致しないため、正規表現のほうが確実である。

    同じアプリが既に開いていると正規表現だけでは古いウィンドウにも一致するため、
    ``existing``（起動前のウィンドウ）に無いものを優先する。新しいものが 1 つも
    無ければ、既存のウィンドウを再利用したとみなして一致の先頭を返す。
    """
    pattern = plan.get("window_title_re")
    try:
        windows = inspector.list_windows(True)
    except Exception:
        return None

    matched: list[ElementInfo] = []
    for window in windows:
        title = window.window_text or ""
        if pattern:
            if title and re.search(pattern, title):
                matched.append(window)
            continue
        if pid is not None and window.process_id == pid and title:
            matched.append(window)

    if existing:
        fresh = [window for window in matched if window.handle not in existing]
        if fresh:
            return fresh[0]
    return matched[0] if matched else None


def _terminate(pid: int) -> None:
    try:
        os.kill(pid, 9)
    except OSError as exc:
        raise ActionFailedError(f"プロセスを終了できませんでした: pid={pid}: {exc}") from exc
