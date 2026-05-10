from __future__ import annotations

from dataclasses import dataclass

from pyselector.model.rectangle import RectangleInfo


@dataclass(frozen=True)
class HierarchyNode:
    depth: int
    window_text: str | None = None
    control_type: str | None = None
    automation_id: str | None = None
    class_name: str | None = None
    friendly_class_name: str | None = None
    control_id: int | None = None
    handle: int | None = None
    rectangle: RectangleInfo | None = None
