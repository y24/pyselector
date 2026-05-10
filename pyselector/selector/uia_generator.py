from __future__ import annotations

from typing import Any

from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.selector_candidate import SelectorCandidate, SelectorStep
from pyselector.utils.text import escape_python_string, escape_regex, is_blank

FOUND_INDEX_TRIAL_COUNT = 3


def generate_uia_candidates(
    element: ElementInfo,
    hierarchy: list[HierarchyNode] | None = None,
    found_index_trial_count: int | None = None,
) -> list[SelectorCandidate]:
    title = None if is_blank(element.window_text) else element.window_text
    auto_id = None if is_blank(element.automation_id) else element.automation_id
    control_type = None if is_blank(element.control_type) else element.control_type
    candidates: list[SelectorCandidate] = []

    if auto_id and control_type:
        candidates.append(
            SelectorCandidate(
                backend="uia",
                selector_text=f'dlg.child_window(auto_id="{escape_python_string(auto_id)}", control_type="{escape_python_string(control_type)}")',
                selector_kind="uia_auto_id_control_type",
                condition={"auto_id": auto_id, "control_type": control_type},
                uses_auto_id=True,
                uses_control_type=True,
                display_order=10,
            )
        )
    if title and auto_id and control_type:
        candidates.append(
            SelectorCandidate(
                backend="uia",
                selector_text=f'dlg.child_window(title="{escape_python_string(title)}", auto_id="{escape_python_string(auto_id)}", control_type="{escape_python_string(control_type)}")',
                selector_kind="uia_title_auto_id_control_type",
                condition={"title": title, "auto_id": auto_id, "control_type": control_type},
                uses_title=True,
                uses_auto_id=True,
                uses_control_type=True,
                display_order=20,
            )
        )
    if auto_id:
        candidates.append(
            SelectorCandidate(
                backend="uia",
                selector_text=f'dlg.child_window(auto_id="{escape_python_string(auto_id)}")',
                selector_kind="uia_auto_id",
                condition={"auto_id": auto_id},
                uses_auto_id=True,
                display_order=30,
            )
        )
    if title and control_type:
        candidates.append(
            SelectorCandidate(
                backend="uia",
                selector_text=f'dlg.child_window(title="{escape_python_string(title)}", control_type="{escape_python_string(control_type)}")',
                selector_kind="uia_title_control_type",
                condition={"title": title, "control_type": control_type},
                uses_title=True,
                uses_control_type=True,
                display_order=40,
            )
        )
        regex = f"^{escape_regex(title)}$"
        candidates.append(
            SelectorCandidate(
                backend="uia",
                selector_text=f'dlg.child_window(title_re="{escape_python_string(regex)}", control_type="{escape_python_string(control_type)}")',
                selector_kind="uia_title_re_control_type",
                condition={"title_re": regex, "control_type": control_type},
                uses_title_re=True,
                uses_control_type=True,
                display_order=50,
            )
        )
    if title:
        candidates.append(
            SelectorCandidate(
                backend="uia",
                selector_text=f'dlg.child_window(title="{escape_python_string(title)}")',
                selector_kind="uia_title",
                condition={"title": title},
                uses_title=True,
                display_order=70,
            )
        )
    candidates.extend(
        _generate_parent_scoped_candidates(
            element,
            hierarchy,
            allow_found_index_fallback=not candidates,
            found_index_trial_count=found_index_trial_count or FOUND_INDEX_TRIAL_COUNT,
        )
    )
    return candidates


def build_uia_found_index_candidate(base: SelectorCandidate, found_index: int) -> SelectorCandidate | None:
    if base.selector_kind != "uia_control_type":
        return None
    control_type = base.condition["control_type"]
    return SelectorCandidate(
        backend="uia",
        selector_text=f'dlg.child_window(control_type="{escape_python_string(control_type)}", found_index={found_index})',
        selector_kind="uia_control_type_found_index",
        condition={"control_type": control_type, "found_index": found_index},
        uses_control_type=True,
        uses_found_index=True,
        display_order=55,
    )


def _generate_parent_scoped_candidates(
    element: ElementInfo,
    hierarchy: list[HierarchyNode] | None,
    allow_found_index_fallback: bool,
    found_index_trial_count: int,
) -> list[SelectorCandidate]:
    if not hierarchy or len(hierarchy) < 2:
        return []
    parent = hierarchy[-2]
    parent_conditions = _parent_conditions(parent)
    target_conditions = _target_conditions(element)
    candidates: list[SelectorCandidate] = []
    order = 35
    for parent_kind, parent_condition in parent_conditions:
        for target_kind, target_condition in target_conditions:
            selector_text = f"{_child_window_expr('dlg', parent_condition)}.{_child_window_call(target_condition)}"
            candidates.append(
                SelectorCandidate(
                    backend="uia",
                    selector_text=selector_text,
                    selector_kind=f"uia_parent_{parent_kind}_target_{target_kind}",
                    condition=target_condition,
                    steps=[
                        SelectorStep(role="ancestor", condition=parent_condition),
                        SelectorStep(role="target", condition=target_condition),
                    ],
                    uses_title=("title" in parent_condition or "title" in target_condition),
                    uses_auto_id=("auto_id" in parent_condition or "auto_id" in target_condition),
                    uses_control_type=("control_type" in parent_condition or "control_type" in target_condition),
                    uses_parent_scope=True,
                    display_order=order,
                )
            )
            order += 1
    if not candidates and allow_found_index_fallback:
        candidates.extend(_generate_parent_found_index_fallback_candidates(element, parent, found_index_trial_count))
    return candidates


def _parent_conditions(parent: HierarchyNode) -> list[tuple[str, dict[str, Any]]]:
    title = None if is_blank(parent.window_text) else parent.window_text
    auto_id = None if is_blank(parent.automation_id) else parent.automation_id
    control_type = None if is_blank(parent.control_type) else parent.control_type
    conditions: list[tuple[str, dict[str, Any]]] = []
    if auto_id and control_type:
        conditions.append(("auto_id_control_type", {"auto_id": auto_id, "control_type": control_type}))
    if title and auto_id and control_type:
        conditions.append(("title_auto_id_control_type", {"title": title, "auto_id": auto_id, "control_type": control_type}))
    if auto_id:
        conditions.append(("auto_id", {"auto_id": auto_id}))
    if title and control_type:
        conditions.append(("title_control_type", {"title": title, "control_type": control_type}))
    return conditions[:4]


def _target_conditions(element: ElementInfo) -> list[tuple[str, dict[str, Any]]]:
    title = None if is_blank(element.window_text) else element.window_text
    auto_id = None if is_blank(element.automation_id) else element.automation_id
    control_type = None if is_blank(element.control_type) else element.control_type
    conditions: list[tuple[str, dict[str, Any]]] = []
    if auto_id and control_type:
        conditions.append(("auto_id_control_type", {"auto_id": auto_id, "control_type": control_type}))
    if title and control_type:
        conditions.append(("title_control_type", {"title": title, "control_type": control_type}))
    if auto_id:
        conditions.append(("auto_id", {"auto_id": auto_id}))
    if title:
        conditions.append(("title", {"title": title}))
    return conditions[:3]


def _generate_parent_found_index_fallback_candidates(
    element: ElementInfo,
    parent: HierarchyNode,
    found_index_trial_count: int,
) -> list[SelectorCandidate]:
    parent_class_name = None if is_blank(parent.class_name) else parent.class_name
    target_class_name = None if is_blank(element.class_name) else element.class_name
    if not parent_class_name or not target_class_name:
        return []
    candidates: list[SelectorCandidate] = []
    for found_index in range(found_index_trial_count):
        parent_condition = {"class_name": parent_class_name, "found_index": found_index}
        target_condition = {"class_name": target_class_name}
        selector_text = f"{_child_window_expr('dlg', parent_condition)}.{_child_window_call(target_condition)}"
        candidates.append(
            SelectorCandidate(
                backend="uia",
                selector_text=selector_text,
                selector_kind="uia_parent_class_name_found_index_target_class_name",
                condition=target_condition,
                steps=[
                    SelectorStep(role="ancestor", condition=parent_condition),
                    SelectorStep(role="target", condition=target_condition),
                ],
                uses_class_name=True,
                uses_found_index=True,
                uses_parent_scope=True,
                display_order=90 + found_index,
            )
        )
    return candidates


def _child_window_expr(prefix: str, condition: dict[str, Any]) -> str:
    return f"{prefix}.{_child_window_call(condition)}"


def _child_window_call(condition: dict[str, Any]) -> str:
    return f"child_window({_format_condition(condition)})"


def _format_condition(condition: dict[str, Any]) -> str:
    parts = []
    for key, value in condition.items():
        if isinstance(value, str):
            parts.append(f'{key}="{escape_python_string(value)}"')
        else:
            parts.append(f"{key}={value}")
    return ", ".join(parts)
