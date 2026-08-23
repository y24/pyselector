from __future__ import annotations

import socket
import struct

from pyselector.server.transport import ConnectionClosed


_LENGTH_PREFIX = struct.Struct("!I")
MAX_MESSAGE_BYTES = 64 * 1024 * 1024


class LoopbackConnection:
    """長さ前置きでメッセージ境界を作る TCP 接続。

    名前付きパイプのメッセージモードと同じ「1 要求 = 1 メッセージ」を再現する。
    """

    def __init__(self, sock: socket.socket) -> None:
        self._socket = sock

    def receive(self) -> bytes:
        header = self._read_exactly(_LENGTH_PREFIX.size)
        (length,) = _LENGTH_PREFIX.unpack(header)
        if length > MAX_MESSAGE_BYTES:
            raise ConnectionClosed(f"message too large: {length}")
        return self._read_exactly(length)

    def send(self, payload: bytes) -> None:
        try:
            self._socket.sendall(_LENGTH_PREFIX.pack(len(payload)) + payload)
        except OSError as exc:
            raise ConnectionClosed(str(exc)) from exc

    def close(self) -> None:
        try:
            self._socket.close()
        except OSError:
            pass

    def _read_exactly(self, size: int) -> bytes:
        chunks = []
        remaining = size
        while remaining > 0:
            try:
                chunk = self._socket.recv(remaining)
            except OSError as exc:
                raise ConnectionClosed(str(exc)) from exc
            if not chunk:
                raise ConnectionClosed("peer closed the connection")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)


class LoopbackTransport:
    """テスト専用のループバック TCP トランスポート。

    本番では使わない。ポートを開けば設計 4.1 の認証の議論をやり直すことになるため、
    サーバーの受付ループを検証する目的だけに留める。ポート 0 で bind するので
    テスト同士がぶつからない。
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0, backlog: int = 16) -> None:
        self._host = host
        self._port = port
        self._backlog = backlog
        self._socket: socket.socket | None = None

    @property
    def address(self) -> tuple[str, int]:
        if self._socket is None:
            raise RuntimeError("transport is not listening")
        host, port = self._socket.getsockname()[:2]
        return (host, port)

    def listen(self) -> None:
        if self._socket is not None:
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self._host, self._port))
        sock.listen(self._backlog)
        self._socket = sock

    def accept(self, timeout: float) -> LoopbackConnection | None:
        if self._socket is None:
            raise RuntimeError("transport is not listening")
        self._socket.settimeout(timeout)
        try:
            client, _ = self._socket.accept()
        except socket.timeout:
            return None
        except OSError:
            return None
        return LoopbackConnection(client)

    def close(self) -> None:
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None


def connect_loopback(address: tuple[str, int], timeout: float) -> LoopbackConnection:
    sock = socket.create_connection(address, timeout=timeout)
    sock.settimeout(timeout)
    return LoopbackConnection(sock)
