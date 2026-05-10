from __future__ import annotations

from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.selector_candidate import SelectorCandidate
from pyselector.selector.uia_generator import generate_uia_candidates
from pyselector.selector.win32_generator import generate_win32_candidates


def generate_candidates(
    element: ElementInfo,
    hierarchy: list[HierarchyNode] | None = None,
    found_index_trial_count: int | None = None,
) -> list[SelectorCandidate]:
    if element.backend == "win32":
        candidates = generate_win32_candidates(element, hierarchy, found_index_trial_count)
    elif element.backend == "uia":
        candidates = generate_uia_candidates(element, hierarchy, found_index_trial_count)
    else:
        candidates = []
    return sort_candidates(deduplicate_candidates(candidates))


def deduplicate_candidates(candidates: list[SelectorCandidate]) -> list[SelectorCandidate]:
    seen: set[tuple[str, str]] = set()
    result: list[SelectorCandidate] = []
    for candidate in candidates:
        key = (candidate.backend, candidate.selector_text)
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result


def sort_candidates(candidates: list[SelectorCandidate]) -> list[SelectorCandidate]:
    return sorted(candidates, key=lambda candidate: candidate.display_order)
