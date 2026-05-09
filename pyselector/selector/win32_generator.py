from __future__ import annotations

from typing import Any

from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.selector_candidate import SelectorCandidate, SelectorStep
from pyselector.utils.text import escape_python_string, is_blank


def generate_win32_candidates(element: ElementInfo, hierarchy: list[HierarchyNode] | None = None) -> list[SelectorCandidate]:
    title = None if is_blank(element.window_text) else element.window_text
    class_name = None if is_blank(element.class_name) else element.class_name
    candidates: list[SelectorCandidate] = []

    if title and class_name:
        candidates.append(
            SelectorCandidate(
                backend="win32",
                selector_text=f'dlg.child_window(title="{escape_python_string(title)}", class_name="{escape_python_string(class_name)}")',
                selector_kind="win32_title_class_name",
                condition={"title": title, "class_name": class_name},
                uses_title=True,
                uses_class_name=True,
                display_order=20,
            )
        )
    if title:
        candidates.append(
            SelectorCandidate(
                backend="win32",
                selector_text=f'dlg.child_window(title="{escape_python_string(title)}")',
                selector_kind="win32_title",
                condition={"title": title},
                uses_title=True,
                display_order=70,
            )
        )
    candidates.extend(_generate_parent_scoped_candidates(element, hierarchy))
    return candidates


def build_win32_class_name_probe_candidate(element: ElementInfo) -> SelectorCandidate | None:
    class_name = None if is_blank(element.class_name) else element.class_name
    if not class_name:
        return None
    return SelectorCandidate(
        backend="win32",
        selector_text=f'dlg.child_window(class_name="{escape_python_string(class_name)}")',
        selector_kind="win32_class_name",
        condition={"class_name": class_name},
        uses_class_name=True,
        display_order=60,
    )


def build_win32_found_index_candidate(base: SelectorCandidate, found_index: int) -> SelectorCandidate | None:
    if base.selector_kind == "win32_class_name":
        class_name = base.condition["class_name"]
        return SelectorCandidate(
            backend="win32",
            selector_text=f'dlg.child_window(class_name="{escape_python_string(class_name)}", found_index={found_index})',
            selector_kind="win32_class_name_found_index",
            condition={"class_name": class_name, "found_index": found_index},
            uses_class_name=True,
            uses_found_index=True,
            display_order=40,
        )
    if base.selector_kind == "win32_title":
        title = base.condition["title"]
        return SelectorCandidate(
            backend="win32",
            selector_text=f'dlg.child_window(title="{escape_python_string(title)}", found_index={found_index})',
            selector_kind="win32_title_found_index",
            condition={"title": title, "found_index": found_index},
            uses_title=True,
            uses_found_index=True,
            display_order=50,
        )
    return None


def _generate_parent_scoped_candidates(
    element: ElementInfo,
    hierarchy: list[HierarchyNode] | None,
) -> list[SelectorCandidate]:
    if not hierarchy or len(hierarchy) < 2:
        return []
    parent = hierarchy[-2]
    parent_conditions = _parent_conditions(parent)
    target_conditions = _target_conditions(element)
    candidates: list[SelectorCandidate] = []
    order = 30
    for parent_kind, parent_condition in parent_conditions:
        for target_kind, target_condition in target_conditions:
            selector_text = f"{_child_window_expr('dlg', parent_condition)}.{_child_window_call(target_condition)}"
            candidates.append(
                SelectorCandidate(
                    backend="win32",
                    selector_text=selector_text,
                    selector_kind=f"win32_parent_{parent_kind}_target_{target_kind}",
                    condition=target_condition,
                    steps=[
                        SelectorStep(role="ancestor", condition=parent_condition),
                        SelectorStep(role="target", condition=target_condition),
                    ],
                    uses_title=("title" in parent_condition or "title" in target_condition),
                    uses_class_name=("class_name" in parent_condition or "class_name" in target_condition),
                    uses_parent_scope=True,
                    display_order=order,
                )
            )
            order += 1
    return candidates


def _parent_conditions(parent: HierarchyNode) -> list[tuple[str, dict[str, Any]]]:
    title = None if is_blank(parent.window_text) else parent.window_text
    class_name = None if is_blank(parent.class_name) else parent.class_name
    conditions: list[tuple[str, dict[str, Any]]] = []
    if title and class_name:
        conditions.append(("title_class_name", {"title": title, "class_name": class_name}))
    return conditions


def _target_conditions(element: ElementInfo) -> list[tuple[str, dict[str, Any]]]:
    title = None if is_blank(element.window_text) else element.window_text
    class_name = None if is_blank(element.class_name) else element.class_name
    conditions: list[tuple[str, dict[str, Any]]] = []
    if title and class_name:
        conditions.append(("title_class_name", {"title": title, "class_name": class_name}))
    if title:
        conditions.append(("title", {"title": title}))
    return conditions[:3]


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
