from __future__ import annotations

import os
import re
import sys
from argparse import Namespace
from dataclasses import dataclass
from typing import Any, Callable

# 下の 5 つは、この module 属性として各コマンドから呼ばれる（common.setup_dpi_awareness など）。
# 直接 import させると差し替えの効かない束縛が各所に散るため、参照点をここ 1 つに集める。
from pyselector.backends.uia_inspector import UiaInspector
from pyselector.backends.win32_inspector import Win32Inspector
from pyselector.countdown import wait_with_countdown
from pyselector.cursor import get_cursor_position
from pyselector.model.element_info import ElementInfo
from pyselector.model.inspection_result import BackendInspection, CursorPosition
from pyselector.model.selector_candidate import SelectorEvaluation
from pyselector.output.json_output import hierarchy_node_to_dict
from pyselector.selector.evaluator import append_found_index_candidates, evaluate_candidates
from pyselector.selector.generator import deduplicate_candidates, generate_candidates, sort_candidates
from pyselector.selector.snippet import build_code_snippet, build_window_snippet
from pyselector.selector.warning import attach_warnings
from pyselector.server import session as server_session
from pyselector.server.refs import ref_backend
from pyselector.utils.dpi import setup_dpi_awareness
from pyselector.utils.errors import ActionNotAllowedError
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
