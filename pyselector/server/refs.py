from __future__ import annotations

from collections import OrderedDict
from typing import Any

from pyselector.utils.errors import StaleRefError


DEFAULT_MAX_REFS = 5000


class RefRegistry:
    """要素参照（ref）と pywinauto wrapper の対応表。

    ref の形式は ``<backend>:<インスタンスID>:<連番>``。インスタンス ID を含めるため、
    サーバーを再起動した後に古い ref を渡されても、表を引くまでもなく失効と判定できる。

    上限を超えた分は最も古いものから追い出す（設計 7.5）。追い出された ref は
    ``stale_ref`` として扱われる。
    """

    def __init__(self, instance_id: str, max_refs: int | None = DEFAULT_MAX_REFS) -> None:
        self.instance_id = instance_id
        self.max_refs = max_refs
        self._counter = 0
        self._wrappers: "OrderedDict[str, Any]" = OrderedDict()

    def issue(self, backend: str, wrapper: Any) -> str:
        self._counter += 1
        ref = f"{backend}:{self.instance_id}:{self._counter}"
        self._wrappers[ref] = wrapper
        self._evict()
        return ref

    def get(self, ref: str) -> Any | None:
        """登録済みなら wrapper を返す。LRU なので参照したものは新しい扱いにする。"""
        if ref not in self._wrappers:
            return None
        self._wrappers.move_to_end(ref)
        return self._wrappers[ref]

    def resolve(self, ref: str) -> Any:
        wrapper = self.get(ref)
        if wrapper is None:
            raise StaleRefError(stale_ref_message(ref))
        return wrapper

    def __len__(self) -> int:
        return len(self._wrappers)

    def _evict(self) -> None:
        if self.max_refs is None:
            return
        while len(self._wrappers) > self.max_refs:
            self._wrappers.popitem(last=False)


def parse_ref(ref: str) -> tuple[str, str, int]:
    """ref を ``(backend, instance_id, 連番)`` に分解する。

    形式が違うものは、その場で失効として扱う。参照表を引く必要すらない。
    """
    parts = ref.split(":")
    if len(parts) != 3:
        raise StaleRefError(stale_ref_message(ref))
    backend, instance_id, serial = parts
    if backend not in ("win32", "uia") or not instance_id or not serial.isdigit():
        raise StaleRefError(stale_ref_message(ref))
    return backend, instance_id, int(serial)


def ref_backend(ref: str) -> str:
    return parse_ref(ref)[0]


def stale_ref_message(ref: str) -> str:
    return f"この参照は無効になっています。find で取得し直してください（{ref}）"
