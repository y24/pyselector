from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NodeChange:
    """前後で同一と判断できたノードのうち、属性が変わったもの。"""

    before: dict[str, Any]
    after: dict[str, Any]
    changes: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class BackendDiff:
    backend: str
    added: list[dict[str, Any]] = field(default_factory=list)
    removed: list[dict[str, Any]] = field(default_factory=list)
    changed: list[NodeChange] = field(default_factory=list)
    unchanged: int = 0
    status: str = "success"
    message: str | None = None

    @property
    def has_differences(self) -> bool:
        return bool(self.added or self.removed or self.changed)
