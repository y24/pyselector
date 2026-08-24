from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BatchStepResult:
    index: int
    argv: list[str]
    exit_code: int
    #: そのステップのエンベロープ。JSON にならなかったときは None。
    result: dict[str, Any] | None = None
    #: JSON にならなかったときの生の出力。原因の手がかりとして残す。
    output: str | None = None


@dataclass(frozen=True)
class BatchResult:
    steps: list[BatchStepResult] = field(default_factory=list)
    requested: int = 0
    #: 停止させた失敗ステップの終了コード。全成功なら 0。
    failed_exit_code: int = 0

    @property
    def completed(self) -> int:
        return len(self.steps)

    @property
    def status(self) -> str:
        return "success" if self.failed_exit_code == 0 else "error"
