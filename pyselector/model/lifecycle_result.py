from __future__ import annotations

from dataclasses import dataclass, field

from pyselector.model.element_info import ElementInfo
from pyselector.model.target_window import TargetWindowInfo


@dataclass(frozen=True)
class LaunchResult:
    backend: str
    exe: str
    args: list[str] = field(default_factory=list)
    window_title_re: str | None = None
    timeout: int = 30
    dry_run: bool = False
    #: 既に起動していたので起動せず接続した。
    attached: bool = False
    pid: int | None = None
    window: ElementInfo | None = None
    target_window: TargetWindowInfo | None = None
    status: str = "success"


@dataclass(frozen=True)
class CloseResult:
    backend: str
    performed: bool = False
    dry_run: bool = False
    forced: bool = False
    method: str | None = None
    window: ElementInfo | None = None
    target_window: TargetWindowInfo | None = None
    status: str = "success"
