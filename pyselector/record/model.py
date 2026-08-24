from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: 記録できる手順の種類。探索（find / tree）は記録しない。
#: 探索は手順ではなく、テストに残す必要が無いため（設計 11 §8.1）。
STEP_KINDS = ("launch", "act", "expect", "close")


@dataclass(frozen=True)
class RecordedSelector:
    """記録した時点で確定していたセレクター。

    ``text`` は ``dlg.child_window(...)`` の形。コード生成時に先頭の変数名だけを
    差し替える。
    """

    text: str
    kind: str
    hits: int | None = None
    warnings: list[str] = field(default_factory=list)
    #: "evaluated"（要素から生成して評価したもの）か "conditions"（探索条件から
    #: 組み立てたもの）か。0 件を確かめる判定には対象要素が存在しないため後者になる。
    source: str = "evaluated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "kind": self.kind,
            "hits": self.hits,
            "warnings": list(self.warnings),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RecordedSelector":
        return cls(
            text=raw.get("text", ""),
            kind=raw.get("kind", ""),
            hits=raw.get("hits"),
            warnings=list(raw.get("warnings") or []),
            source=raw.get("source", "evaluated"),
        )


@dataclass(frozen=True)
class RecordedStep:
    seq: int
    kind: str
    timestamp: str
    backend: str = "uia"
    #: act なら操作名（click など）、expect なら判定名（exists など）。
    action: str | None = None
    #: act で実際に成功した pywinauto のメソッド名。生成コードはこれをそのまま使う。
    method: str | None = None
    value: Any = None
    expected: Any = None
    selector: RecordedSelector | None = None
    #: セレクターを確定できなかった理由。生成コードにコメントとして残す。
    selector_warning: str | None = None
    element: dict[str, Any] = field(default_factory=dict)
    target_window: dict[str, Any] = field(default_factory=dict)
    #: {"timeout": 5} 形式。expect --wait / act --settle で記録される。
    wait: dict[str, Any] | None = None
    launch: dict[str, Any] | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "kind": self.kind,
            "timestamp": self.timestamp,
            "backend": self.backend,
            "action": self.action,
            "method": self.method,
            "value": self.value,
            "expected": self.expected,
            "selector": self.selector.to_dict() if self.selector else None,
            "selector_warning": self.selector_warning,
            "element": dict(self.element),
            "target_window": dict(self.target_window),
            "wait": dict(self.wait) if self.wait else None,
            "launch": dict(self.launch) if self.launch else None,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RecordedStep":
        selector = raw.get("selector")
        return cls(
            seq=int(raw.get("seq", 0)),
            kind=raw.get("kind", "act"),
            timestamp=raw.get("timestamp", ""),
            backend=raw.get("backend", "uia"),
            action=raw.get("action"),
            method=raw.get("method"),
            value=raw.get("value"),
            expected=raw.get("expected"),
            selector=RecordedSelector.from_dict(selector) if selector else None,
            selector_warning=raw.get("selector_warning"),
            element=dict(raw.get("element") or {}),
            target_window=dict(raw.get("target_window") or {}),
            wait=dict(raw["wait"]) if raw.get("wait") else None,
            launch=dict(raw["launch"]) if raw.get("launch") else None,
            note=raw.get("note"),
        )


@dataclass(frozen=True)
class Recording:
    name: str
    started_at: str
    version: str
    steps: list[RecordedStep] = field(default_factory=list)

    @property
    def next_seq(self) -> int:
        return len(self.steps) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "started_at": self.started_at,
            "version": self.version,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Recording":
        return cls(
            name=raw.get("name", ""),
            started_at=raw.get("started_at", ""),
            version=raw.get("version", ""),
            steps=[RecordedStep.from_dict(step) for step in raw.get("steps") or []],
        )
