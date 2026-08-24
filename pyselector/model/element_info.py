from __future__ import annotations

from dataclasses import dataclass

from pyselector.model.rectangle import RectangleInfo


@dataclass(frozen=True)
class ElementInfo:
    backend: str
    window_text: str | None = None
    control_type: str | None = None
    automation_id: str | None = None
    class_name: str | None = None
    friendly_class_name: str | None = None
    control_id: int | None = None
    children_count: int | None = None
    depth: int | None = None
    rectangle: RectangleInfo | None = None
    is_visible: bool | None = None
    is_enabled: bool | None = None
    handle: int | None = None
    process_id: int | None = None
    process_name: str | None = None
    ref: str | None = None
    # 以下は要素の「状態」。走査時には読まず、出力対象が確定してから
    # read_element_state() で埋める（設計 11 §3.2）。取得できなければ None。
    value: str | None = None
    is_checked: bool | None = None
    is_selected: bool | None = None
    is_offscreen: bool | None = None
    has_keyboard_focus: bool | None = None

    @property
    def has_state(self) -> bool:
        """状態属性が 1 つでも取得できているか。"""
        return any(
            getattr(self, name) is not None
            for name in ("value", "is_checked", "is_selected", "is_offscreen", "has_keyboard_focus")
        )
