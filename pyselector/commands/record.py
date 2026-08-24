from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from pyselector.commands.common import _use_color
from pyselector.output.json_output import format_recording_json
from pyselector.record import store
from pyselector.record.codegen import emit
from pyselector.utils.errors import ArgumentError
from pyselector.utils.logging import info_log


def run_record(args: Namespace) -> int:
    action = args.record_command
    if action == "start":
        return _start(args)
    if action == "status":
        return _status(args)
    if action == "show":
        return _show(args)
    if action == "stop":
        return _stop(args)
    if action == "cancel":
        return _cancel(args)
    raise ArgumentError(f"未対応の record サブコマンドです: {action}")


def _start(args: Namespace) -> int:
    existing = store.load()
    if existing is not None and not args.force:
        raise ArgumentError(
            f"すでに「{existing.name}」を記録中です（手順 {len(existing.steps)} 件）。"
            "続きを記録するならそのまま操作を、破棄するなら record cancel を、"
            "上書きするなら --force を指定してください"
        )
    recording = store.start(args.name)
    _report(args, "record", recording, f"記録を開始しました: {recording.name}")
    return 0


def _status(args: Namespace) -> int:
    recording = store.load()
    if recording is None:
        _report(args, "record", None, "記録していません。")
        return 1
    _report(args, "record", recording, f"記録中: {recording.name}（手順 {len(recording.steps)} 件）")
    return 0


def _show(args: Namespace) -> int:
    recording = store.load()
    if recording is None:
        _report(args, "record", None, "記録していません。")
        return 1
    if getattr(args, "json", False):
        print(format_recording_json("record", recording), end="")
        return 0
    color = _use_color()
    info_log(f"記録中: {recording.name}", color)
    for step in recording.steps:
        selector = step.selector.text if step.selector else "(セレクター未確定)"
        label = f"{step.seq}. {step.kind}: {step.action}"
        print(f"  {label}\n     {selector}")
    return 0


def _stop(args: Namespace) -> int:
    recording = store.load()
    if recording is None:
        _report(args, "record", None, "記録していません。")
        return 1

    if args.emit == "none":
        code = None
    else:
        code = emit(recording, args.emit)

    target = Path(args.out) if args.out else None
    if target is not None and code is not None:
        if target.exists() and not args.force:
            # 生成物を黙って上書きしない。人が手を入れた後かもしれない。
            raise ArgumentError(f"すでに存在します: {target}（上書きするなら --force）")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8", newline="\n")

    store.clear()

    if getattr(args, "json", False):
        extra: dict[str, object] = {"emit": args.emit, "path": str(target) if target else None}
        if code is not None and target is None:
            extra["code"] = code
        print(format_recording_json("record", recording, extra), end="")
        return 0

    if code is not None and target is None:
        print(code, end="" if code.endswith("\n") else "\n")
    elif target is not None:
        info_log(f"書き出しました: {target}", _use_color())
    else:
        info_log(f"記録を終了しました（手順 {len(recording.steps)} 件）", _use_color())
    return 0


def _cancel(args: Namespace) -> int:
    cleared = store.clear()
    if not cleared:
        _report(args, "record", None, "記録していません。")
        return 1
    _report(args, "record", None, "記録を破棄しました。")
    return 0


def _report(args: Namespace, command: str, recording, message: str) -> None:
    if getattr(args, "json", False):
        print(format_recording_json(command, recording, {"message": message}), end="")
        return
    info_log(message, _use_color())
