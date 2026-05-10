from __future__ import annotations

import time
from typing import Any

from pyselector.model.element_info import ElementInfo
from pyselector.model.inspection_result import CursorPosition
from pyselector.model.selector_candidate import SelectorCandidate, SelectorEvaluation
from pyselector.selector.uia_generator import build_uia_found_index_candidate
from pyselector.selector.win32_generator import build_win32_found_index_candidate


def evaluate_candidates(
    candidates: list[SelectorCandidate],
    inspector: Any,
    scope: dict[str, Any],
    timeout_sec: int,
    max_items: int | None,
    target: ElementInfo | None = None,
    cursor_position: CursorPosition | None = None,
    stop_after_first_found_index_match: bool = False,
) -> list[SelectorEvaluation]:
    evaluations: list[SelectorEvaluation] = []
    start = time.monotonic()
    for candidate in candidates:
        if time.monotonic() - start > timeout_sec:
            evaluations.append(SelectorEvaluation(candidate=candidate, hits=None, status="timeout"))
            break
        condition = dict(candidate.condition)
        if max_items is not None:
            condition["_max_items"] = max_items
        try:
            if candidate.steps:
                matches, reached_limit, parent_hits = _evaluate_steps(inspector, scope, candidate, max_items)
                hits = len(matches)
            elif "found_index" in condition:
                found_index = condition.pop("found_index")
                hits, reached_limit, matches = _evaluate_found_index(inspector, scope, condition, found_index, max_items)
                parent_hits = None
            else:
                matches, reached_limit = inspector.find_elements(scope, condition)
                hits = len(matches)
                parent_hits = None
            if target is not None and hits == 1 and not _matches_target(matches, target, cursor_position):
                hits = 0
            evaluation = SelectorEvaluation(
                candidate=candidate,
                hits=hits,
                status="success",
                reached_limit=reached_limit,
                parent_hits=parent_hits,
            )
            setattr(evaluation, "_matches", matches)
            evaluations.append(evaluation)
            if (
                stop_after_first_found_index_match
                and _is_parent_found_index_trial(candidate)
                and hits == 1
                and target is not None
                and _matches_target(matches, target, cursor_position)
            ):
                break
        except Exception as exc:
            evaluations.append(
                SelectorEvaluation(
                    candidate=candidate,
                    hits=None,
                    status="error",
                    error_message=str(exc),
                )
            )
    return evaluations


def append_found_index_candidates(
    candidates: list[SelectorCandidate],
    evaluations: list[SelectorEvaluation],
    target: ElementInfo,
) -> list[SelectorCandidate]:
    extra: list[SelectorCandidate] = []
    for evaluation in evaluations:
        if evaluation.status != "success" or evaluation.hits is None or evaluation.hits <= 1:
            continue
        if evaluation.candidate.uses_found_index:
            continue
        found_index = _find_index_from_cache(evaluation, target)
        if found_index is None:
            continue
        builder = build_win32_found_index_candidate if target.backend == "win32" else build_uia_found_index_candidate
        candidate = builder(evaluation.candidate, found_index)
        if candidate is not None:
            extra.append(candidate)
    return candidates + extra


def _evaluate_steps(
    inspector: Any,
    scope: dict[str, Any],
    candidate: SelectorCandidate,
    max_items: int | None,
) -> tuple[list[ElementInfo], bool, int | None]:
    if hasattr(inspector, "find_elements_chain"):
        return inspector.find_elements_chain(scope, [step.condition for step in candidate.steps], max_items)
    return [], False, None


def _evaluate_found_index(
    inspector: Any,
    scope: dict[str, Any],
    condition: dict[str, Any],
    found_index: int,
    max_items: int | None,
) -> tuple[int, bool, list[ElementInfo]]:
    if max_items is not None:
        condition["_max_items"] = max_items
    matches, reached_limit = inspector.find_elements(scope, condition)
    if 0 <= found_index < len(matches):
        return 1, False, [matches[found_index]]
    return 0, reached_limit, []


def _find_index_from_cache(evaluation: SelectorEvaluation, target: ElementInfo) -> int | None:
    matches = getattr(evaluation, "_matches", None)
    if not matches:
        return None
    for index, element in enumerate(matches):
        if elements_match(element, target):
            return index
    return None


def _matches_target(matches: list[ElementInfo], target: ElementInfo, cursor_position: CursorPosition | None = None) -> bool:
    if len(matches) != 1:
        return False
    match = matches[0]
    if cursor_position is not None and _contains_point(match, cursor_position):
        return True
    return elements_match(match, target)


def _contains_point(element: ElementInfo, cursor_position: CursorPosition) -> bool:
    rect = element.rectangle
    if rect is None:
        return False
    return rect.left <= cursor_position.x < rect.right and rect.top <= cursor_position.y < rect.bottom


def _is_parent_found_index_trial(candidate: SelectorCandidate) -> bool:
    return candidate.selector_kind.endswith("_parent_class_name_found_index_target_class_name")


def elements_match(left: ElementInfo, right: ElementInfo) -> bool:
    if left.handle is not None and right.handle is not None:
        return left.handle == right.handle
    if left.rectangle is not None and right.rectangle is not None:
        return left.rectangle == right.rectangle
    if left.backend == "win32":
        return (
            left.control_id == right.control_id
            and left.class_name == right.class_name
            and left.window_text == right.window_text
        )
    return (
        left.automation_id == right.automation_id
        and left.control_type == right.control_type
        and left.window_text == right.window_text
    )
