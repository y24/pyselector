from __future__ import annotations

from pyselector.model.element_info import ElementInfo
from pyselector.model.selector_candidate import SelectorCandidate
from pyselector.utils.text import escape_python_string, is_blank


def generate_win32_candidates(element: ElementInfo) -> list[SelectorCandidate]:
    title = None if is_blank(element.window_text) else element.window_text
    class_name = None if is_blank(element.class_name) else element.class_name
    candidates: list[SelectorCandidate] = []

    if element.control_id is not None and class_name:
        candidates.append(
            SelectorCandidate(
                backend="win32",
                selector_text=f'dlg.child_window(control_id={element.control_id}, class_name="{escape_python_string(class_name)}")',
                selector_kind="win32_control_id_class_name",
                condition={"control_id": element.control_id, "class_name": class_name},
                uses_control_id=True,
                uses_class_name=True,
                display_order=10,
            )
        )
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
    if element.control_id is not None:
        candidates.append(
            SelectorCandidate(
                backend="win32",
                selector_text=f"dlg.child_window(control_id={element.control_id})",
                selector_kind="win32_control_id",
                condition={"control_id": element.control_id},
                uses_control_id=True,
                display_order=30,
            )
        )
    if class_name:
        candidates.append(
            SelectorCandidate(
                backend="win32",
                selector_text=f'dlg.child_window(class_name="{escape_python_string(class_name)}")',
                selector_kind="win32_class_name",
                condition={"class_name": class_name},
                uses_class_name=True,
                display_order=60,
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
    if element.handle is not None:
        candidates.append(
            SelectorCandidate(
                backend="win32",
                selector_text=f"dlg.child_window(handle=0x{element.handle:X})",
                selector_kind="win32_handle",
                condition={"handle": element.handle},
                uses_handle=True,
                display_order=1000,
            )
        )
    return candidates


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
