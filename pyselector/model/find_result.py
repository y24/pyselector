from __future__ import annotations

from dataclasses import dataclass, field

from pyselector.model.element_info import ElementInfo
from pyselector.model.inspection_result import BackendInspection


@dataclass(frozen=True)
class FindMatch:
    element: ElementInfo
    inspection: BackendInspection | None = None

    @property
    def point(self) -> tuple[int, int] | None:
        if self.element.rectangle is None:
            return None
        return self.element.rectangle.center


@dataclass(frozen=True)
class FindResult:
    backend: str
    root: ElementInfo | None = None
    matches: list[FindMatch] = field(default_factory=list)
    scanned: int = 0
    total_matched: int = 0
    reached_limit: bool = False
    truncated: bool = False
    status: str = "success"
    message: str | None = None
