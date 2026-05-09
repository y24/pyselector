from __future__ import annotations

import time
from typing import Any

from pyselector.model.element_info import ElementInfo
from pyselector.model.selector_candidate import SelectorCandidate, SelectorEvaluation
from pyselector.selector.uia_generator import build_uia_found_index_candidate
from pyselector.selector.win32_generator import build_win32_found_index_candidate


def evaluate_candidates(
    candidates: list[SelectorCandidate],
    inspector: Any,
    scope: dict[str, Any],
    timeout_sec: int,
    max_items: int | None,
) -> list[SelectorEvaluation]:
    evaluations: list[SelectorEvaluation] = []
    start = time.monotonic()
    for candidate in candidates:
        if time.monotonic() - start > timeout_sec:
            evaluations.append(SelectorEvaluation(candidate=candidate, hits=None, status="timeout"))
            continue
        condition = dict(candidate.condition)
        if max_items is not None:
            condition["_max_items"] = max_items
        try:
            if "found_index" in condition:
                found_index = condition.pop("found_index")
                hits, reached_limit = _evaluate_found_index(inspector, scope, condition, found_index, max_items)
            else:
                matches, reached_limit = inspector.find_elements(scope, condition)
                hits = len(matches)
            evaluation = SelectorEvaluation(
                candidate=candidate,
                hits=hits,
                status="success",
                reached_limit=reached_limit,
            )
            setattr(evaluation, "_matches", matches if "found_index" not in candidate.condition else [])
            evaluations.append(evaluation)
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


def _evaluate_found_index(inspector: Any, scope: dict[str, Any], condition: dict[str, Any], found_index: int, max_items: int | None) -> tuple[int, bool]:
    if max_items is not None:
        condition["_max_items"] = max_items
    matches, reached_limit = inspector.find_elements(scope, condition)
    return (1 if 0 <= found_index < len(matches) else 0), reached_limit


def _find_index_from_cache(evaluation: SelectorEvaluation, target: ElementInfo) -> int | None:
    matches = getattr(evaluation, "_matches", None)
    if not matches:
        return None
    for index, element in enumerate(matches):
        if elements_match(element, target):
            return index
    return None


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
