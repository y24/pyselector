from __future__ import annotations

from dataclasses import dataclass, field

from pyselector.model.rectangle import RectangleInfo


@dataclass(frozen=True)
class WindowSummary:
    backend: str
    title: str | None = None
    class_name: str | None = None
    process_name: str | None = None
    process_id: int | None = None
    handle: int | None = None
    rectangle: RectangleInfo | None = None
    is_visible: bool | None = None
    is_enabled: bool | None = None


@dataclass(frozen=True)
class WindowsResult:
    backend: str
    windows: list[WindowSummary] = field(default_factory=list)
    reached_limit: bool = False
    status: str = "success"
    message: str | None = None
