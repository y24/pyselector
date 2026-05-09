from __future__ import annotations

from dataclasses import dataclass, field

from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.selector_candidate import SelectorCandidate, SelectorEvaluation
from pyselector.model.target_window import TargetWindowInfo


@dataclass(frozen=True)
class CursorPosition:
    x: int
    y: int


@dataclass
class BackendInspection:
    backend: str
    element: ElementInfo | None = None
    target_window: TargetWindowInfo | None = None
    hierarchy: list[HierarchyNode] = field(default_factory=list)
    candidates: list[SelectorCandidate] = field(default_factory=list)
    evaluations: list[SelectorEvaluation] = field(default_factory=list)
    code_snippet: str | None = None
    status: str = "success"
    message: str | None = None


@dataclass(frozen=True)
class InspectionResult:
    cursor_position: CursorPosition
    win32: BackendInspection | None = None
    uia: BackendInspection | None = None


@dataclass(frozen=True)
class TreeResult:
    backend: str
    root: ElementInfo | None
    nodes: list[HierarchyNode]
    reached_limit: bool
    status: str = "success"
    message: str | None = None
