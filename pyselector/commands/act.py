from __future__ import annotations

from argparse import Namespace
from typing import Any, Callable

from pyselector.commands import common
from pyselector.commands.common import (
    _build_backend_inspection,
    _ensure_actions_allowed,
    _candidate_hint,
    _element_center,
    _has_element_conditions,
    _info_logger,
    _matches_find_predicates,
    _resolve_find_root,
    _selector_options_from_args,
    _snapshot_nodes,
    _sort_find_elements,
    _use_color,
)
from pyselector.diff import diff_nodes
from pyselector.model.act_result import ActResult
from pyselector.model.element_info import ElementInfo
from pyselector.output.json_output import format_act_result_json
from pyselector.record import capture as record_capture
from pyselector.output.text_output import format_act_result
from pyselector.server.refs import ref_backend
from pyselector.utils.errors import AmbiguousTargetError, ElementNotFoundError
from pyselector.utils.logging import info_log
from pyselector.wait import DEFAULT_POLL_INTERVAL, poll_until_stable

def run_act(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    common.setup_dpi_awareness()

    ref = getattr(args, "ref", None)
    backend = ref_backend(ref) if ref is not None else args.backend
    action = args.action
    value = getattr(args, "value", None)
    dry_run = getattr(args, "dry_run", False)
    if not dry_run:
        _ensure_actions_allowed(args)

    inspector = common._create_inspector(backend)
    target, target_window = _resolve_act_target(inspector, backend, args, log)

    diff_result = None
    diff_handle = target_window.handle if getattr(args, "diff", False) else None
    before_nodes: list[Any] = []
    if diff_handle is not None:
        log(f"{backend}: 操作前のUI要素ツリーを取得中です...")
        before_nodes = _snapshot_nodes(backend, diff_handle, args)

    method = None
    performed = False
    element_after = None
    if dry_run:
        log(f"{backend}: --dry-run のため操作は実行しません。")
    else:
        log(f"{backend}: {action} を実行中です...")
        method = inspector.perform_action(target, action, value)
        performed = True
        log(f"{backend}: {action} を実行しました。（{method}）")
        try:
            element_after = inspector.refresh_element(target)
        except Exception:
            element_after = None

    settle = getattr(args, "settle", None)
    settle_outcome = None
    settled_nodes: list[Any] | None = None
    settle_handle = target_window.handle
    if performed and settle and settle_handle is not None:
        log(f"{backend}: 画面が落ち着くまで待機中です... (最大 {settle}秒)")
        settled_nodes, settle_outcome = poll_until_stable(
            lambda: _snapshot_nodes(backend, settle_handle, args),
            timeout=settle,
            poll_interval=getattr(args, "poll_interval", DEFAULT_POLL_INTERVAL),
        )
        state = "変化が止まりませんでした" if settle_outcome.timed_out else "落ち着きました"
        log(f"{backend}: {state}（{settle_outcome.rounded}秒 / {settle_outcome.attempts}回）")

    if diff_handle is not None and performed:
        # --settle と併用したときは、安定した後のツリーをそのまま操作後として使う。
        # 取り直すと、待った意味が薄れるうえ余分な走査が 1 回増える。
        if settled_nodes is not None:
            after_nodes = settled_nodes
        else:
            log(f"{backend}: 操作後のUI要素ツリーを取得中です...")
            after_nodes = _snapshot_nodes(backend, diff_handle, args)
        diff_result = diff_nodes(backend, before_nodes, after_nodes)

    recorded = None
    if performed:
        recorded = record_capture.record_act(
            args,
            backend,
            inspector,
            target,
            target_window,
            method,
            lambda: _build_backend_inspection(
                backend, inspector, target, _element_center(target), _selector_options_from_args(args), log
            ),
            log,
        )
        if recorded is not None:
            log(f"記録しました。手順 {recorded.seq}")

    result = ActResult(
        backend=backend,
        action=action,
        value=value,
        performed=performed,
        dry_run=dry_run,
        method=method,
        target=target,
        target_window=target_window,
        element_after=element_after,
        diff=diff_result,
    )
    output = (
        format_act_result_json(result, outcome=settle_outcome, recorded=recorded)
        if json_output
        else format_act_result(result, color)
    )
    print(output, end="")
    return 0


def _resolve_act_target(
    inspector: Any,
    backend: str,
    args: Namespace,
    log: Callable[[str], None],
) -> tuple[ElementInfo, Any]:
    ref = getattr(args, "ref", None)
    if ref is not None and not _has_element_conditions(args):
        # ref は操作対象そのものを指す。生存確認は element_from_ref が行うので、
        # 失効していればここで止まり、別の要素を操作することはない（設計 7.4）。
        log(f"{backend}: ref {ref} の要素を取得中です...")
        target = inspector.element_from_ref(ref)
        return target, inspector.get_target_window(target)

    at = getattr(args, "at", None)
    if at is not None:
        log(f"{backend}: 座標 X={at[0]}, Y={at[1]} の要素を取得中です...")
        target = inspector.element_from_point(at[0], at[1])
        return target, inspector.get_target_window(target)

    root = _resolve_find_root(inspector, backend, args, log)
    log(f"{backend}: 操作対象を検索中です... (depth={args.depth}, max-items={args.max_items})")
    elements, _ = inspector.walk_elements(root, args.depth, args.max_items, args.only_visible, None)
    matched = _sort_find_elements([element for element in elements if _matches_find_predicates(element, args)])
    index = getattr(args, "index", None)
    if index is not None:
        if index >= len(matched):
            raise ElementNotFoundError(f"条件に一致した要素は {len(matched)} 件で、index={index} は範囲外です")
        target = matched[index]
    elif not matched:
        raise ElementNotFoundError("条件に一致する要素がありません")
    elif len(matched) > 1:
        raise AmbiguousTargetError(
            f"条件に一致する要素が {len(matched)} 件あります。"
            f"条件を絞るか --index で選んでください{_candidate_hint(matched)}"
        )
    else:
        target = matched[0]
    log(f"{backend}: 操作対象を特定しました。{target.window_text!r}")
    return target, inspector.get_target_window(target)
