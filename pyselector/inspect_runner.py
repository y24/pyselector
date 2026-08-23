from __future__ import annotations

import os
import re
import sys
import time
from argparse import Namespace
from dataclasses import dataclass
from typing import Any, Callable

from pyselector.backends.uia_inspector import UiaInspector
from pyselector.backends.win32_inspector import Win32Inspector
from pyselector.countdown import wait_with_countdown
from pyselector.cursor import get_cursor_position
from pyselector.diff import diff_nodes, diff_tree_payloads, load_tree_payload
from pyselector.model.act_result import ActResult
from pyselector.model.element_info import ElementInfo
from pyselector.model.find_result import FindMatch, FindResult
from pyselector.model.inspection_result import BackendInspection, CursorPosition, InspectionResult, TreeResult
from pyselector.model.window_summary import WindowSummary, WindowsResult
from pyselector.overlay.selector_overlay import select_point_with_overlay
from pyselector.model.selector_candidate import SelectorEvaluation
from pyselector.output.json_output import (
    format_act_result_json,
    format_diff_results_json,
    format_find_results_json,
    format_inspection_result_json,
    format_tree_results_json,
    format_windows_results_json,
    hierarchy_node_to_dict,
)
from pyselector.output.log_file import save_inspection_log
from pyselector.output.text_output import (
    format_act_result,
    format_diff_result,
    format_find_result,
    format_inspection_result,
    format_tree_result,
    format_windows_result,
)
from pyselector.selector.evaluator import append_found_index_candidates, evaluate_candidates
from pyselector.selector.generator import generate_candidates, sort_candidates, deduplicate_candidates
from pyselector.selector.snippet import build_code_snippet, build_window_snippet
from pyselector.selector.warning import attach_warnings
from pyselector.server import session as server_session
from pyselector.server.refs import ref_backend
from pyselector.utils.dpi import setup_dpi_awareness
from pyselector.utils.errors import (
    ActionNotAllowedError,
    AmbiguousTargetError,
    ElementNotFoundError,
    StaleRefError,
)
from pyselector.utils.logging import info_log
from pyselector.utils.process import get_process_name


DEFAULT_SELECTOR_EVALUATION_MAX_ITEMS = 10
OVERLAY_CLOSE_WAIT_SECONDS = 0.05


@dataclass(frozen=True)
class SelectorBuildOptions:
    """セレクター候補の生成・評価に必要な設定。"""

    scope: str = "window"
    only_visible: bool = True
    timeout: int = 5
    detail: bool = False
    evaluation_max_items: int = DEFAULT_SELECTOR_EVALUATION_MAX_ITEMS
    found_index_trial_count: int | None = None


def run_inspect(args: Namespace, point_selector: Callable[[], tuple[int, int] | None] | None = None) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    config_path = getattr(args, "config_path", None)
    if config_path is not None and not json_output:
        info_log(f"{config_path.name} loaded", color)
    setup_dpi_awareness()
    handle = getattr(args, "handle", None)
    ref = getattr(args, "ref", None)
    if ref is not None:
        # ref は要素そのものを指す。座標を選ぶ手順を通らないので、
        # cursor_position は解決した要素の中心を参考情報として載せる。
        resolved = _create_inspector(ref_backend(ref)).element_from_ref(ref)
        point = _element_point(resolved)
    else:
        point = _select_inspect_point(args, color, json_output, point_selector)
    if point is None:
        if not json_output:
            info_log("選択をキャンセルしました。", color)
        return 1
    cursor = CursorPosition(x=point[0], y=point[1])

    options = _selector_options_from_args(args)
    inspections: list[BackendInspection] = []
    for backend in _resolve_backends(args.backend, ref):
        inspector = _create_inspector(backend)
        try:
            if ref is not None:
                log(f"{backend}: ref {ref} の要素を取得中です...")
                element = inspector.element_from_ref(ref)
            elif handle is None:
                log(f"{backend}: カーソル下の要素を取得中です...")
                element = inspector.element_from_point(cursor.x, cursor.y)
            else:
                log(f"{backend}: handle {handle:#x} の要素を取得中です...")
                element = inspector.element_from_handle(handle)
            inspections.append(_build_backend_inspection(backend, inspector, element, cursor, options, log))
        except StaleRefError:
            # 失効した ref は backend 単位の失敗ではなく、要求そのものの失敗として返す。
            raise
        except Exception as exc:
            inspections.append(BackendInspection(backend=backend, status="failed", message=str(exc)))

    result = InspectionResult(
        cursor_position=cursor,
        win32=_find_backend(inspections, "win32"),
        uia=_find_backend(inspections, "uia"),
    )
    output = (
        format_inspection_result_json(result)
        if json_output
        else format_inspection_result(result, args.detail, color, include_cursor=True)
    )
    print(output, end="")
    log_output = format_inspection_result_json(result) if json_output else format_inspection_result(result, args.detail, False, include_cursor=False)
    save_inspection_log(result, log_output, suffix=".json" if json_output else ".txt")
    return 0 if any(item.status == "success" for item in inspections) else 1


def _build_backend_inspection(
    backend: str,
    inspector: Any,
    element: ElementInfo,
    cursor: CursorPosition | None,
    options: SelectorBuildOptions,
    log: Callable[[str], None],
) -> BackendInspection:
    """要素からセレクター候補の生成・評価・スニペット化までを行う。

    inspect と find で共有する。
    """
    log(f"{backend}: 対象ウィンドウを特定中です...")
    target_window = inspector.get_target_window(element)
    log(f"{backend}: 親子階層を取得中です...")
    hierarchy = inspector.get_hierarchy(element)
    found_index_trial_count = options.found_index_trial_count
    candidates = (
        generate_candidates(element, hierarchy, found_index_trial_count)
        if found_index_trial_count is not None
        else generate_candidates(element, hierarchy)
    )
    scope = {
        "scope": options.scope,
        "target_handle": target_window.handle,
        "only_visible": options.only_visible,
    }
    log(f"{backend}: セレクター候補を評価中です... ({len(candidates)}件)")
    evaluations = evaluate_candidates(candidates, inspector, scope, options.timeout, options.evaluation_max_items)
    log(f"{backend}: セレクター候補の評価が完了しました。ヒット候補: {_count_hit_evaluations(evaluations)}件")
    if not _has_single_hit_evaluation(evaluations):
        fallback_candidates = (
            generate_candidates(
                element,
                hierarchy,
                found_index_trial_count,
                include_parent_found_index_fallback=True,
            )
            if found_index_trial_count is not None
            else generate_candidates(element, hierarchy, include_parent_found_index_fallback=True)
        )
        candidates = deduplicate_candidates(sort_candidates(candidates + fallback_candidates))
    candidates = deduplicate_candidates(sort_candidates(append_found_index_candidates(candidates, evaluations, element)))
    log(f"{backend}: セレクター候補を再評価中です... ({len(candidates)}件)")
    evaluations = evaluate_candidates(
        candidates,
        inspector,
        scope,
        options.timeout,
        options.evaluation_max_items,
        target=element,
        cursor_position=cursor,
        stop_after_first_found_index_match=True,
    )
    log(f"{backend}: セレクター候補の再評価が完了しました。ヒット候補: {_count_hit_evaluations(evaluations)}件")
    attach_warnings(evaluations, element, options.detail)
    evaluations = _exclude_unmatched_evaluations(evaluations)
    snippet = build_code_snippet(backend, target_window, evaluations)
    if snippet is None and _is_target_window_itself(element, target_window):
        snippet = build_window_snippet(backend, target_window)
    return BackendInspection(
        backend=backend,
        element=element,
        target_window=target_window,
        hierarchy=hierarchy,
        candidates=candidates,
        evaluations=evaluations,
        code_snippet=snippet,
    )


def _is_target_window_itself(element: ElementInfo, target_window: Any) -> bool:
    handle = getattr(target_window, "handle", None)
    return handle is not None and element.handle == handle


def _selector_options_from_args(args: Namespace) -> SelectorBuildOptions:
    max_items = getattr(args, "max_items", None)
    evaluation_max_items = max_items or getattr(
        args, "selector_evaluation_max_items", DEFAULT_SELECTOR_EVALUATION_MAX_ITEMS
    )
    return SelectorBuildOptions(
        scope=getattr(args, "scope", "window"),
        only_visible=getattr(args, "only_visible", True),
        timeout=getattr(args, "timeout", 5),
        detail=getattr(args, "detail", False),
        evaluation_max_items=evaluation_max_items,
        found_index_trial_count=getattr(args, "found_index_trial_count", None),
    )


def _select_inspect_point(
    args: Namespace,
    color: bool,
    json_output: bool,
    point_selector: Callable[[], tuple[int, int] | None] | None,
) -> tuple[int, int] | None:
    if point_selector is not None:
        point = point_selector()
        if point is not None:
            time.sleep(OVERLAY_CLOSE_WAIT_SECONDS)
        return point

    at = getattr(args, "at", None)
    if at is not None:
        return at

    handle = getattr(args, "handle", None)
    if handle is not None:
        return _window_center(handle)

    delay = getattr(args, "delay", None)
    if delay is None:
        point = select_point_with_overlay()
        if point is not None:
            time.sleep(OVERLAY_CLOSE_WAIT_SECONDS)
        return point

    if json_output:
        time.sleep(delay)
    else:
        wait_with_countdown(delay, color)
    cursor = get_cursor_position()
    return (cursor.x, cursor.y)


def _window_center(handle: int) -> tuple[int, int]:
    """handle 指定時の cursor_position 用に、ウィンドウ矩形の中心を返す。

    要素自体は handle から解決するため、この座標は参考情報として出力する。
    """
    try:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(handle), ctypes.byref(rect)):
            return (0, 0)
        return ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
    except Exception:
        return (0, 0)


def run_tree(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    setup_dpi_awareness()
    ref = getattr(args, "ref", None)
    backends = _resolve_backends(args.backend, ref)
    cursor = None
    if args.cursor:
        if json_output:
            time.sleep(args.delay)
        else:
            wait_with_countdown(args.delay, color)
        cursor = get_cursor_position()
        log(f"座標を決定しました。 X={cursor.x}, Y={cursor.y}")

    window_handle = getattr(args, "window_handle", None)
    results: list[TreeResult] = []
    for backend in backends:
        inspector = _create_inspector(backend)
        try:
            if ref is not None:
                log(f"{backend}: ref {ref} の起点要素を取得中です...")
                root = inspector.element_from_ref(ref)
            elif cursor is not None:
                log(f"{backend}: カーソル下の起点要素を取得中です...")
                root = inspector.element_from_point(cursor.x, cursor.y)
            elif window_handle is not None:
                log(f"{backend}: handle {window_handle:#x} のウィンドウを取得中です...")
                root = inspector.find_window_by_handle(window_handle)
            else:
                log(f"{backend}: 対象ウィンドウを検索中です...")
                root = inspector.find_window_by_title(args.window_title, args.title_re)
            log(f"{backend}: UI要素ツリーを取得中です... (depth={args.depth}, max-items={args.max_items})")
            nodes, reached_limit = inspector.walk_tree(
                root,
                args.depth,
                args.max_items,
                args.only_visible,
                None if json_output else _tree_progress_logger(backend, color),
            )
            log(f"{backend}: UI要素ツリーの取得が完了しました。表示要素: {len(nodes)}件")
            results.append(
                TreeResult(
                    backend=backend,
                    root=root,
                    nodes=nodes,
                    reached_limit=reached_limit,
                )
            )
        except StaleRefError:
            raise
        except Exception as exc:
            results.append(
                TreeResult(
                    backend=backend,
                    root=None,
                    nodes=[],
                    reached_limit=False,
                    status="failed",
                    message=str(exc),
                )
            )
    summary = getattr(args, "summary", False)
    compact = getattr(args, "compact", False)
    output = (
        format_tree_results_json(results, summary=summary, compact=compact)
        if json_output
        else "".join(
            format_tree_result(result, args.detail, color, include_heading=index == 0, summary=summary)
            for index, result in enumerate(results)
        )
    )
    print(output, end="")
    return 0 if any(result.status == "success" for result in results) else 1


def run_windows(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    setup_dpi_awareness()

    results: list[WindowsResult] = []
    for backend in _resolve_backends(args.backend):
        inspector = _create_inspector(backend)
        try:
            log(f"{backend}: ウィンドウ一覧を取得中です...")
            elements = inspector.list_windows(args.only_visible)
            summaries = _filter_windows(_to_window_summaries(elements, backend), args)
            reached_limit = len(summaries) > args.max_items
            log(f"{backend}: ウィンドウ一覧の取得が完了しました。該当: {len(summaries)}件")
            results.append(
                WindowsResult(
                    backend=backend,
                    windows=summaries[: args.max_items],
                    reached_limit=reached_limit,
                )
            )
        except Exception as exc:
            results.append(WindowsResult(backend=backend, status="failed", message=str(exc)))

    compact = getattr(args, "compact", False)
    output = (
        format_windows_results_json(results, compact=compact)
        if json_output
        else "".join(
            format_windows_result(result, color, include_heading=index == 0)
            for index, result in enumerate(results)
        )
    )
    print(output, end="")
    if not any(result.status == "success" for result in results):
        return 1
    return 0 if any(result.windows for result in results) else 1


def run_find(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    setup_dpi_awareness()

    options = _selector_options_from_args(args)
    results: list[FindResult] = []
    for backend in _resolve_backends(args.backend, getattr(args, "ref", None)):
        inspector = _create_inspector(backend)
        try:
            root = _resolve_find_root(inspector, backend, args, log)
            log(f"{backend}: 要素を走査中です... (depth={args.depth}, max-items={args.max_items})")
            elements, reached_limit = inspector.walk_elements(
                root,
                args.depth,
                args.max_items,
                args.only_visible,
                None if json_output else _find_progress_logger(backend, color),
            )
            matched = _sort_find_elements([element for element in elements if _matches_find_predicates(element, args)])
            log(f"{backend}: 走査が完了しました。走査 {len(elements)}件 / 一致 {len(matched)}件")
            total_matched = len(matched)
            truncated = total_matched > args.limit
            matched = matched[: args.limit]
            matches: list[FindMatch] = []
            for index, element in enumerate(matched):
                inspection = None
                if getattr(args, "with_selectors", False) and index < args.selector_limit:
                    inspection = _build_backend_inspection(
                        backend,
                        inspector,
                        element,
                        _element_center(element),
                        options,
                        log,
                    )
                matches.append(FindMatch(element=element, inspection=inspection))
            results.append(
                FindResult(
                    backend=backend,
                    root=root,
                    matches=matches,
                    scanned=len(elements),
                    total_matched=total_matched,
                    reached_limit=reached_limit,
                    truncated=truncated,
                )
            )
        except StaleRefError:
            raise
        except Exception as exc:
            results.append(FindResult(backend=backend, status="failed", message=str(exc)))

    compact = getattr(args, "compact", False)
    output = (
        format_find_results_json(results, compact=compact)
        if json_output
        else "".join(
            format_find_result(result, args.detail, color, include_heading=index == 0)
            for index, result in enumerate(results)
        )
    )
    print(output, end="")
    if not any(result.status == "success" for result in results):
        return 1
    return 0 if any(result.matches for result in results) else 1


def run_act(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    setup_dpi_awareness()

    ref = getattr(args, "ref", None)
    backend = ref_backend(ref) if ref is not None else args.backend
    action = args.action
    value = getattr(args, "value", None)
    dry_run = getattr(args, "dry_run", False)
    if not dry_run:
        _ensure_actions_allowed(args)

    inspector = _create_inspector(backend)
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

    if diff_handle is not None and performed:
        log(f"{backend}: 操作後のUI要素ツリーを取得中です...")
        after_nodes = _snapshot_nodes(backend, diff_handle, args)
        diff_result = diff_nodes(backend, before_nodes, after_nodes)

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
    output = format_act_result_json(result) if json_output else format_act_result(result, color)
    print(output, end="")
    return 0


def _ensure_actions_allowed(args: Namespace) -> None:
    """UI 操作を実行してよいかを確かめる。

    本質的な関門から順に見る。.env とコマンドのフラグが「この操作を許すか」を決め、
    常駐サーバーの上限は「このデーモンに UI を触らせるか」という別の軸なので最後に見る。
    順序を逆にすると、.env を書いていないだけの利用者に的外れな理由を返してしまう。
    """
    if not getattr(args, "env_allow_actions", False):
        raise ActionNotAllowedError(
            "UI 操作は既定で無効です。.env に PYSELECTOR_ALLOW_ACTIONS=true を書いてください"
        )
    if not getattr(args, "allow_actions", False):
        raise ActionNotAllowedError("UI 操作には --allow-actions の指定が必要です")
    session = server_session.current_session()
    if session is not None and not session.allow_actions:
        # 設定もフラグも揃っているのに、このデーモンだけが UI 操作を持たない状態。
        # 自動起動なら設定を引き継ぐので、ここに来るのは手動起動したサーバーか、
        # act を許可していない別のディレクトリから先に自動起動された場合。
        raise ActionNotAllowedError(
            "この常駐サーバーは UI 操作を許可していません。"
            "pyselector serve --stop で止めてから pyselector serve --allow-actions で"
            "起動し直すか、--server off でローカル実行してください"
        )


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


def _candidate_hint(elements: list[ElementInfo], max_items: int = 5) -> str:
    listed = ", ".join(
        f"[{index}] {element.window_text!r}" for index, element in enumerate(elements[:max_items])
    )
    suffix = ", ..." if len(elements) > max_items else ""
    return f"（{listed}{suffix}）"


def _snapshot_nodes(backend: str, window_handle: int, args: Namespace) -> list[dict[str, Any]]:
    """操作前後の比較用に、対象ウィンドウのツリーを取り直す。"""
    inspector = _create_inspector(backend)
    root = inspector.find_window_by_handle(window_handle)
    nodes, _ = inspector.walk_tree(root, args.depth, args.max_items, args.only_visible, None)
    return [hierarchy_node_to_dict(node) for node in nodes]


def run_diff(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    if not json_output:
        info_log("pyselector started", color)
    before = load_tree_payload(args.before)
    after = load_tree_payload(args.after)
    diffs = diff_tree_payloads(before, after)
    output = (
        format_diff_results_json(diffs, compact=getattr(args, "compact", False))
        if json_output
        else "".join(
            format_diff_result(diff, color, include_heading=index == 0)
            for index, diff in enumerate(diffs)
        )
    )
    print(output, end="")
    if not any(diff.status == "success" for diff in diffs):
        return 1
    return 0 if any(diff.has_differences for diff in diffs) else 1


def _resolve_find_root(inspector: Any, backend: str, args: Namespace, log: Callable[[str], None]) -> ElementInfo:
    ref = getattr(args, "ref", None)
    if ref is not None:
        log(f"{backend}: ref {ref} の起点要素を取得中です...")
        return inspector.element_from_ref(ref)
    at = getattr(args, "at", None)
    if at is not None:
        log(f"{backend}: 座標 X={at[0]}, Y={at[1]} の起点要素を取得中です...")
        return inspector.element_from_point(at[0], at[1])
    window_handle = getattr(args, "window_handle", None)
    if window_handle is not None:
        log(f"{backend}: handle {window_handle:#x} のウィンドウを取得中です...")
        return inspector.find_window_by_handle(window_handle)
    log(f"{backend}: 対象ウィンドウを検索中です...")
    return inspector.find_window_by_title(args.window_title, args.title_re)


def _matches_find_predicates(element: ElementInfo, args: Namespace) -> bool:
    text = getattr(args, "text", None)
    if text is not None and text.casefold() not in (element.window_text or "").casefold():
        return False
    text_re = getattr(args, "text_re", None)
    if text_re is not None and re.search(text_re, element.window_text or "") is None:
        return False
    auto_id = getattr(args, "auto_id", None)
    if auto_id is not None and element.automation_id != auto_id:
        return False
    control_type = getattr(args, "control_type", None)
    if control_type is not None and (element.control_type or "").casefold() != control_type.casefold():
        return False
    class_name = getattr(args, "class_name", None)
    if class_name is not None and element.class_name != class_name:
        return False
    if getattr(args, "enabled_only", False) and element.is_enabled is not True:
        return False
    return True


def _sort_find_elements(elements: list[ElementInfo]) -> list[ElementInfo]:
    def sort_key(element: ElementInfo) -> tuple[int, int, int]:
        rectangle = element.rectangle
        return (
            element.depth if element.depth is not None else 0,
            rectangle.top if rectangle is not None else 0,
            rectangle.left if rectangle is not None else 0,
        )

    return sorted(elements, key=sort_key)


def _has_element_conditions(args: Namespace) -> bool:
    """act で ref を探索の起点として使っているか、対象そのものとして使っているかを分ける。"""
    named = ("text", "text_re", "auto_id", "control_type", "class_name")
    if any(getattr(args, name, None) is not None for name in named):
        return True
    return bool(getattr(args, "enabled_only", False)) or getattr(args, "index", None) is not None


def _element_point(element: ElementInfo) -> tuple[int, int]:
    if element.rectangle is None:
        return (0, 0)
    return element.rectangle.center


def _element_center(element: ElementInfo) -> CursorPosition | None:
    if element.rectangle is None:
        return None
    x, y = element.rectangle.center
    return CursorPosition(x=x, y=y)


def _to_window_summaries(elements: list[ElementInfo], backend: str) -> list[WindowSummary]:
    return [
        WindowSummary(
            backend=backend,
            title=element.window_text,
            class_name=element.class_name,
            process_name=get_process_name(element.process_id),
            process_id=element.process_id,
            handle=element.handle,
            rectangle=element.rectangle,
            is_visible=element.is_visible,
            is_enabled=element.is_enabled,
        )
        for element in elements
    ]


def _filter_windows(windows: list[WindowSummary], args: Namespace) -> list[WindowSummary]:
    title = getattr(args, "title", None)
    title_re = getattr(args, "title_re", False)
    process = getattr(args, "process", None)
    pid = getattr(args, "pid", None)
    include_untitled = getattr(args, "include_untitled", False)
    filtered = []
    for window in windows:
        window_title = window.title or ""
        if not window_title and not include_untitled:
            continue
        if title is not None:
            if title_re:
                if re.search(title, window_title) is None:
                    continue
            elif title.casefold() not in window_title.casefold():
                continue
        if process is not None and process.casefold() not in (window.process_name or "").casefold():
            continue
        if pid is not None and window.process_id != pid:
            continue
        filtered.append(window)
    return filtered


def _resolve_backends(value: str, ref: str | None = None) -> list[str]:
    """走査する backend を決める。

    ref は backend を自分で名乗るため、--backend より優先する。ref が指す
    wrapper は片方の backend にしか存在せず、もう一方は必ず失敗するため。
    """
    if ref is not None:
        return [ref_backend(ref)]
    return ["win32", "uia"] if value == "both" else [value]


def _create_inspector(backend: str) -> Any:
    """backend に対応する inspector を返す。

    常駐モードではサーバーのセッションが同じ inspector を使い回す。そうしないと
    要求ごとに pywinauto の wrapper が捨てられ、ref がすべて失効してしまう。
    """
    session = server_session.current_session()
    if session is not None:
        return session.inspector(backend, _new_inspector)
    return _new_inspector(backend)


def _new_inspector(backend: str) -> Any:
    if backend == "win32":
        return Win32Inspector()
    if backend == "uia":
        return UiaInspector()
    raise ValueError(f"unsupported backend: {backend}")


def _info_logger(json_output: bool, color: bool) -> Callable[[str], None]:
    def log(message: str) -> None:
        if not json_output:
            info_log(message, color)

    return log


def _tree_progress_logger(backend: str, color: bool) -> Callable[[int, int], None]:
    def log_progress(done: int, total: int) -> None:
        info_log(f"{backend}: UI要素ツリー取得中... {done}件完了", color)

    return log_progress


def _find_progress_logger(backend: str, color: bool) -> Callable[[int, int], None]:
    def log_progress(done: int, total: int) -> None:
        info_log(f"{backend}: 要素を走査中... {done}件完了", color)

    return log_progress


def _find_backend(inspections: list[BackendInspection], backend: str) -> BackendInspection | None:
    for inspection in inspections:
        if inspection.backend == backend:
            return inspection
    return None


def _exclude_unmatched_evaluations(evaluations: list[SelectorEvaluation]) -> list[SelectorEvaluation]:
    return [
        evaluation
        for evaluation in evaluations
        if evaluation.hits != 0 and not _is_failed_parent_found_index_trial(evaluation)
    ]


def _is_failed_parent_found_index_trial(evaluation: SelectorEvaluation) -> bool:
    return (
        "_parent_class_name_found_index_target_" in evaluation.candidate.selector_kind
        and evaluation.status != "success"
    )


def _count_hit_evaluations(evaluations: list[SelectorEvaluation]) -> int:
    return sum(1 for evaluation in evaluations if evaluation.hits is not None and evaluation.hits > 0)


def _has_single_hit_evaluation(evaluations: list[SelectorEvaluation]) -> bool:
    return any(evaluation.hits == 1 for evaluation in evaluations)


def _use_color() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ
