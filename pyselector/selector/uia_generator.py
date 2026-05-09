from __future__ import annotations

from pyselector.model.element_info import ElementInfo
from pyselector.model.selector_candidate import SelectorCandidate
from pyselector.utils.text import escape_python_string, escape_regex, is_blank


def generate_uia_candidates(element: ElementInfo) -> list[SelectorCandidate]:
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
    if control_type:
        candidates.append(
            SelectorCandidate(
                backend="uia",
                selector_text=f'dlg.child_window(control_type="{escape_python_string(control_type)}")',
                selector_kind="uia_control_type",
                condition={"control_type": control_type},
                uses_control_type=True,
                display_order=60,
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
