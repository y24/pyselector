from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SelectorCandidate:
    backend: str
    selector_text: str
    selector_kind: str
    condition: dict[str, Any]
    uses_title: bool = False
    uses_title_re: bool = False
    uses_class_name: bool = False
    uses_auto_id: bool = False
    uses_control_type: bool = False
    uses_found_index: bool = False
    display_order: int = 0


@dataclass
class SelectorEvaluation:
    candidate: SelectorCandidate
    hits: int | None
    status: str = "success"
    warnings: list[str] = field(default_factory=list)
    reached_limit: bool = False
    error_message: str | None = None
