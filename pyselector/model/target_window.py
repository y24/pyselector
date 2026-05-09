from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetWindowInfo:
    backend: str
    title: str | None = None
    class_name: str | None = None
    process_name: str | None = None
    process_id: int | None = None
    handle: int | None = None
