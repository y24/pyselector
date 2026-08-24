from __future__ import annotations

from dataclasses import dataclass, field

from pyselector.model.element_info import ElementInfo


@dataclass(frozen=True)
class Annotation:
    """画像に描き込んだ枠 1 つ分。番号は 1 始まり。"""

    index: int
    element: ElementInfo


@dataclass(frozen=True)
class ShotResult:
    backend: str
    path: str
    width: int
    height: int
    #: 画像の左上に対応する画面座標。要素の rectangle と画像内の位置を突き合わせるために出す。
    origin: tuple[int, int] = (0, 0)
    target: ElementInfo | None = None
    annotations: list[Annotation] = field(default_factory=list)
    status: str = "success"
