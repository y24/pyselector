from __future__ import annotations

from typing import Optional

try:
    from typing import Protocol
except ImportError:  # pragma: no cover - Python 3.7 以前は対象外
    Protocol = object  # type: ignore[assignment]


class ConnectionClosed(Exception):
    """相手が応答を待たずに切断した。"""


class Connection(Protocol):
    """1 要求 = 1 応答の接続。使い終えたら閉じる。"""

    def receive(self) -> bytes: ...

    def send(self, payload: bytes) -> None: ...

    def close(self) -> None: ...


class Transport(Protocol):
    """接続の受け口。

    本番で使うのは名前付きパイプ実装のみ。テストではループバック TCP 実装を使い、
    受付ループを本物のソケット越しに検証する（設計 4.5）。
    """

    def listen(self) -> None: ...

    def accept(self, timeout: float) -> Optional[Connection]:
        """接続を 1 つ受け付ける。timeout 秒のあいだ来なければ None を返す。

        None が返ることがアイドル判定の材料になる。
        """
        ...

    def close(self) -> None: ...
