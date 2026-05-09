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
from pyselector.output.text_output import format_inspection_result, format_tree_result
from pyselector.selector.evaluator import append_found_index_candidates, evaluate_candidates
from pyselector.selector.generator import generate_candidates, sort_candidates, deduplicate_candidates
from pyselector.selector.snippet import build_code_snippet
from pyselector.selector.warning import attach_warnings


def run_inspect(args: Namespace) -> int:
    print("[INFO] pyselector started")
    print(f"[INFO] countdown: {args.delay} sec")
    wait_with_countdown(args.delay)
    cursor = get_cursor_position()

    inspections: list[BackendInspection] = []
    for backend in _resolve_backends(args.backend):
        inspector = _create_inspector(backend)
        try:
            element = inspector.element_from_point(cursor.x, cursor.y)
            target_window = inspector.get_target_window(element)
            hierarchy = inspector.get_hierarchy(element)
            candidates = generate_candidates(element)
            scope = {
                "scope": args.scope,
                "target_handle": target_window.handle,
                "only_visible": args.only_visible,
            }
            evaluations = evaluate_candidates(candidates, inspector, scope, args.timeout, args.max_items)
            candidates = deduplicate_candidates(sort_candidates(append_found_index_candidates(candidates, evaluations, element)))
            evaluations = evaluate_candidates(candidates, inspector, scope, args.timeout, args.max_items)
            attach_warnings(evaluations, element, args.detail)
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
    print(format_inspection_result(result, args.detail, _use_color()), end="")
    return 0 if any(item.status == "success" for item in inspections) else 1


def run_tree(args: Namespace) -> int:
    inspector = _create_inspector(args.backend)
    try:
        if args.cursor:
            wait_with_countdown(args.delay)
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


def _use_color() -> bool:
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ
