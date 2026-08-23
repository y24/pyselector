"""ループバック TCP 越しにサーバーを動かすためのテスト補助。

設計 4.5 のとおり、サーバーのロジックは偽チャネルではなく本物のソケット越しに
検証する。ポート 0 で bind するのでテスト同士がぶつからない。
"""

from __future__ import annotations

import threading
from contextlib import contextmanager

from pyselector import __version__
from pyselector.server.client import ServerClient
from pyselector.server.loopback import LoopbackTransport, connect_loopback
from pyselector.server.protocol import CONTROL_STOP, Request
from pyselector.server.server import Server

POLL_SECONDS = 0.02
CONNECT_TIMEOUT = 30.0


class RunningServer:
    def __init__(self, server: Server, address: tuple[str, int]) -> None:
        self.server = server
        self.address = address

    def client(self, version: str = __version__) -> ServerClient:
        return ServerClient(connect=self._connect, version=version)

    def request(self, argv, cwd, version: str = __version__):
        return self.client(version).request(list(argv), str(cwd), CONNECT_TIMEOUT)

    def send(self, request, version: str = __version__):
        return self.client(version).send(request, CONNECT_TIMEOUT)

    def _connect(self, timeout: float):
        return connect_loopback(self.address, timeout)


@contextmanager
def running_server(**kwargs):
    """スレッドでサーバーを回し、終了まで面倒を見る。"""
    transport = LoopbackTransport()
    transport.listen()
    kwargs.setdefault("idle_timeout", 30)
    kwargs.setdefault("write_state_file", False)
    server = Server(transport, **kwargs)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_seconds": POLL_SECONDS}, daemon=True)
    thread.start()
    running = RunningServer(server, transport.address)
    try:
        yield running
    finally:
        # stop は control 要求で送る。executor を通らないので、テストが記録した
        # 呼び出し履歴に後片付けの分が混ざらない。
        running.send(Request(control=CONTROL_STOP, version=server.version))
        thread.join(timeout=5)


def echo_executor(recorder: list) -> callable:
    """argv と cwd をそのまま記録する executor。UI に触れずに転送だけを見る。"""

    import os

    def execute(argv: list[str]) -> int:
        recorder.append({"argv": list(argv), "cwd": os.getcwd()})
        print(" ".join(argv))
        return 0

    return execute
