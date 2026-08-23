from __future__ import annotations

from typing import Any

from pyselector.server.refs import RefRegistry


class ServerSession:
    """1 つの常駐サーバーが要求をまたいで保持する状態。

    inspector を使い回すことで pywinauto の wrapper が生き残り、要素参照（ref）を
    コマンドをまたいで解決できるようになる。これが常駐化の主目的（設計 1.2）。
    """

    def __init__(self, instance_id: str, max_refs: int = 5000, allow_actions: bool = False) -> None:
        self.instance_id = instance_id
        self.allow_actions = allow_actions
        self.refs = RefRegistry(instance_id, max_refs)
        self._inspectors: dict[str, Any] = {}

    def inspector(self, backend: str, factory) -> Any:
        """backend ごとの inspector を使い回す。

        毎回作り直すと wrapper の参照表が失われ、ref がすべて失効してしまう。
        """
        inspector = self._inspectors.get(backend)
        if inspector is None:
            inspector = factory(backend)
            inspector.use_ref_registry(self.refs)
            self._inspectors[backend] = inspector
        return inspector


_current: ServerSession | None = None


def current_session() -> ServerSession | None:
    return _current


def is_serving() -> bool:
    """いまサーバー内でコマンドを実行しているか。

    出力に ``served`` と ``ref`` を載せるかどうかの判定に使う。
    """
    return _current is not None


def activate(session: ServerSession) -> None:
    global _current
    _current = session


def deactivate() -> None:
    global _current
    _current = None
