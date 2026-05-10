from __future__ import annotations

import os
import sys
from argparse import Namespace
from typing import Any

from pyselector.backends.uia_inspector import UiaInspector
from pyselector.backends.win32_inspector import Win32Inspector
from pyselector.countdown import wait_with_countdown
from pyselector.cursor import get_cursor_position
from pyselector.model.inspection_result import BackendInspection, InspectionResult, TreeResult
from pyselector.model.selector_candidate import SelectorEvaluation
from pyselector.output.text_output import format_inspection_result, format_tree_result
from pyselector.selector.evaluator import append_found_index_candidates, evaluate_candidates
from pyselector.selector.generator import generate_candidates, sort_candidates, deduplicate_candidates
from pyselector.selector.snippet import build_code_snippet
from pyselector.selector.warning import attach_warnings
from pyselector.utils.logging import info_log


DEFAULT_SELECTOR_EVALUATION_MAX_ITEMS = 10


def run_inspect(args: Namespace) -> int:
    color = _use_color()
    info_log("pyselector started", color)
    config_path = getattr(args, "config_path", None)
    if config_path is not None:
        info_log(f"{config_path.name} loaded", color)
    info_log(f"selector validation total timeout: {args.timeout} sec", color)
    wait_with_countdown(args.delay, color)
    cursor = get_cursor_position()
    info_log(f"cursor position: X={cursor.x}, Y={cursor.y}", color)

    inspections: list[BackendInspection] = []
    evaluation_max_items = args.max_items or getattr(args, "selector_evaluation_max_items", DEFAULT_SELECTOR_EVALUATION_MAX_ITEMS)
    for backend in _resolve_backends(args.backend):
        inspector = _create_inspector(backend)
        try:
            element = inspector.element_from_point(cursor.x, cursor.y)
            info_log(f"{backend}: 対象ウィンドウを特定中です...", color)
            target_window = inspector.get_target_window(element)
            info_log(f"{backend}: 親子階層を取得中です...", color)
            hierarchy = inspector.get_hierarchy(element)
            found_index_trial_count = getattr(args, "found_index_trial_count", None)
            candidates = (
                generate_candidates(element, hierarchy, found_index_trial_count)
                if found_index_trial_count is not None
                else generate_candidates(element, hierarchy)
            )
            scope = {
                "scope": args.scope,
                "target_handle": target_window.handle,
                "only_visible": args.only_visible,
            }
            info_log(f"{backend}: セレクター候補を評価中です... ({len(candidates)}件)", color)
            evaluations = evaluate_candidates(candidates, inspector, scope, args.timeout, evaluation_max_items)
            info_log(f"{backend}: セレクター候補の評価が完了しました。ヒット候補: {_count_hit_evaluations(evaluations)}件", color)
            candidates = deduplicate_candidates(sort_candidates(append_found_index_candidates(candidates, evaluations, element)))
            info_log(f"{backend}: セレクター候補を再評価中です... ({len(candidates)}件)", color)
            evaluations = evaluate_candidates(
                candidates,
                inspector,
                scope,
                args.timeout,
                evaluation_max_items,
                target=element,
                cursor_position=cursor,
                stop_after_first_found_index_match=True,
            )
            info_log(f"{backend}: セレクター候補の再評価が完了しました。ヒット候補: {_count_hit_evaluations(evaluations)}件", color)
            attach_warnings(evaluations, element, args.detail)
            evaluations = _exclude_unmatched_evaluations(evaluations)
            snippet = build_code_snippet(backend, target_window, evaluations)
            inspections.append(
                BackendInspection(
                    backend=backend,
                    element=element,
                    target_window=target_window,
                    hierarchy=hierarchy,
                    candidates=candidates,
                    evaluations=evaluations,
                    code_snippet=snippet,
                )
            )
        except Exception as exc:
            inspections.append(BackendInspection(backend=backend, status="failed", message=str(exc)))

    result = InspectionResult(
        cursor_position=cursor,
        win32=_find_backend(inspections, "win32"),
        uia=_find_backend(inspections, "uia"),
    )
    print(format_inspection_result(result, args.detail, color, include_cursor=False), end="")
    return 0 if any(item.status == "success" for item in inspections) else 1


def run_tree(args: Namespace) -> int:
    inspector = _create_inspector(args.backend)
    try:
        if args.cursor:
            wait_with_countdown(args.delay, _use_color())
            cursor = get_cursor_position()
            root = inspector.element_from_point(cursor.x, cursor.y)
        else:
            root = inspector.find_window_by_title(args.window_title, args.title_re)
        nodes, reached_limit = inspector.walk_tree(root, args.depth, args.max_items, args.only_visible)
        result = TreeResult(
            backend=args.backend,
            root=root,
            nodes=nodes,
            reached_limit=reached_limit,
        )
        print(format_tree_result(result, args.detail, _use_color()), end="")
        return 0
    except Exception as exc:
        result = TreeResult(
            backend=args.backend,
            root=None,
            nodes=[],
            reached_limit=False,
            status="failed",
            message=str(exc),
        )
        print(format_tree_result(result, args.detail, _use_color()), end="")
        return 1


def _resolve_backends(value: str) -> list[str]:
    return ["win32", "uia"] if value == "both" else [value]


def _create_inspector(backend: str) -> Any:
    if backend == "win32":
        return Win32Inspector()
    if backend == "uia":
        return UiaInspector()
    raise ValueError(f"unsupported backend: {backend}")


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
        evaluation.candidate.selector_kind.endswith("_parent_class_name_found_index_target_class_name")
        and evaluation.status != "success"
    )


def _count_hit_evaluations(evaluations: list[SelectorEvaluation]) -> int:
    return sum(1 for evaluation in evaluations if evaluation.hits is not None and evaluation.hits > 0)


def _use_color() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ
