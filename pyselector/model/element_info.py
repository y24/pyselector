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
