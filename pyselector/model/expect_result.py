from __future__ import annotations

from dataclasses import dataclass, field

from pyselector.model.find_result import FindResult


#: 判定の種類。値を伴うもの、対象が一意であることを要求するものを分けて扱う。
EXPECTATION_KINDS = (
    "exists",
    "not_exists",
    "count",
    "value_equals",
    "value_contains",
    "checked",
    "unchecked",
    "enabled",
    "disabled",
)

#: 対象がちょうど 1 件に定まらないと判定できない種類。
#: 複数一致したときは act と同じく ambiguous_target で止める。
UNIQUE_TARGET_KINDS = frozenset(
    {"value_equals", "value_contains", "checked", "unchecked", "enabled", "disabled"}
)

#: 要素の状態（value / is_checked）を読む必要がある種類。
STATE_KINDS = frozenset({"value_equals", "value_contains", "checked", "unchecked"})


@dataclass(frozen=True)
class Expectation:
    """何を期待し、実際は何だったか。"""

    kind: str
    expected: object | None = None
    actual: object | None = None


@dataclass(frozen=True)
class ExpectResult:
    expectation: Expectation
    satisfied: bool
    matched: int
    results: list[FindResult] = field(default_factory=list)
    status: str = "success"
    message: str | None = None
