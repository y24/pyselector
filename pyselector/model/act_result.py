from __future__ import annotations

from dataclasses import dataclass

from pyselector.model.diff_result import BackendDiff
from pyselector.model.element_info import ElementInfo
from pyselector.model.target_window import TargetWindowInfo


@dataclass(frozen=True)
class ActResult:
    backend: str
    action: str
    value: str | None = None
    performed: bool = False
    dry_run: bool = False
    method: str | None = None
    target: ElementInfo | None = None
    target_window: TargetWindowInfo | None = None
    element_after: ElementInfo | None = None
    diff: BackendDiff | None = None
    status: str = "success"
    message: str | None = None

    @property
    def point(self) -> tuple[int, int] | None:
        if self.target is None or self.target.rectangle is None:
            return None
        return self.target.rectangle.center
