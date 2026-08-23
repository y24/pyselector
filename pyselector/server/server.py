from __future__ import annotations

import contextlib
import io
import os
import time
import uuid
from typing import Any, Callable

from pyselector import __version__
from pyselector.config import CONFIG_ENV_VAR
from pyselector.server import session as session_module
from pyselector.server.protocol import (
    CONTROL_PING,
    CONTROL_STOP,
    ERROR_COMMAND_NOT_ALLOWED,
    ERROR_MALFORMED_REQUEST,
    ERROR_PROTOCOL_MISMATCH,
    ERROR_VERSION_MISMATCH,
    PROTOCOL_VERSION,
    ProtocolError,
    Request,
    Response,
    SERVER_COMMANDS,
    command_of,
    decode_request,
    encode_response,
)
from pyselector.server.session import ServerSession
from pyselector.server.state import ServerState, clear_state, now_text, write_state
from pyselector.server.transport import ConnectionClosed
from pyselector.utils.errors import EXIT_UNEXPECTED

DEFAULT_IDLE_TIMEOUT = 300
DEFAULT_MAX_REFS = 5000
#: accept の待ち時間。アイドル判定の粒度になる。
ACCEPT_POLL_SECONDS = 1.0


def new_instance_id() -> str:
    return uuid.uuid4().hex[:6]


class Server:
    """要求を逐次処理する常駐サーバー。

    pywinauto と COM はスレッド安全ではないため、単一スレッドで 1 件ずつ処理する
    （設計 4.6）。処理中に来たクライアントはトランスポート側で待たされる。
    """

    def __init__(
        self,
        transport: Any,
        idle_timeout: float = DEFAULT_IDLE_TIMEOUT,
        allow_actions: bool = False,
        max_refs: int = DEFAULT_MAX_REFS,
        instance_id: str | None = None,
        executor: Callable[[list[str]], int] | None = None,
        clock: Callable[[], float] = time.monotonic,
        write_state_file: bool = True,
        version: str = __version__,
    ) -> None:
        self.transport = transport
        self.idle_timeout = idle_timeout
        self.allow_actions = allow_actions
        self.version = version
        self.instance_id = instance_id or new_instance_id()
        self.session = ServerSession(self.instance_id, max_refs=max_refs, allow_actions=allow_actions)
        self._executor = executor or _default_executor
        self._clock = clock
        self._write_state_file = write_state_file
        self._stopping = False
        self.handled_requests = 0

    def serve_forever(self, poll_seconds: float | None = None) -> None:
        """要求を受け続ける。

        ``idle_timeout`` が 0 以下なら時間では終了せず、``--stop`` を待つ。
        自分でプロセスを管理したい場合のための逃げ道。
        """
        poll = poll_seconds if poll_seconds is not None else _poll_interval(self.idle_timeout)
        self.transport.listen()
        self._write_state()
        try:
            last_activity = self._clock()
            while not self._stopping:
                connection = self.transport.accept(poll)
                if connection is None:
                    if self.idle_timeout > 0 and self._clock() - last_activity >= self.idle_timeout:
                        break
                    continue
                try:
                    self.serve_connection(connection)
                finally:
                    connection.close()
                last_activity = self._clock()
        finally:
            self.transport.close()
            self._clear_state()

    def serve_connection(self, connection: Any) -> Response:
        """1 接続 = 1 要求 1 応答を処理する。"""
        try:
            payload = connection.receive()
        except ConnectionClosed:
            return Response(exit_code=EXIT_UNEXPECTED, error=ERROR_MALFORMED_REQUEST)
        response = self.handle_payload(payload)
        try:
            connection.send(encode_response(response))
        except ConnectionClosed:
            pass
        self.handled_requests += 1
        return response

    def handle_payload(self, payload: bytes) -> Response:
        try:
            request = decode_request(payload)
        except ProtocolError as exc:
            return Response(
                exit_code=EXIT_UNEXPECTED,
                error=ERROR_MALFORMED_REQUEST,
                message=str(exc),
                instance_id=self.instance_id,
            )
        return self.handle_request(request)

    def handle_request(self, request: Request) -> Response:
        if request.protocol != PROTOCOL_VERSION:
            return self._reject(
                ERROR_PROTOCOL_MISMATCH,
                f"プロトコル版数が違います（サーバー {PROTOCOL_VERSION} / クライアント {request.protocol}）",
            )
        if request.control == CONTROL_STOP:
            self._stopping = True
            return Response(stdout="", exit_code=0, instance_id=self.instance_id)
        if request.control == CONTROL_PING:
            return Response(stdout="", exit_code=0, instance_id=self.instance_id)
        if request.control is not None:
            return self._reject(ERROR_MALFORMED_REQUEST, f"未知の control です: {request.control}")
        if request.version and request.version != self.version:
            return self._reject(
                ERROR_VERSION_MISMATCH,
                f"常駐サーバーの版数が違います（サーバー {self.version} / クライアント {request.version}）",
            )
        command = command_of(request.argv)
        if command not in SERVER_COMMANDS:
            return self._reject(ERROR_COMMAND_NOT_ALLOWED, f"サーバーで実行しないコマンドです: {command}")
        return self._execute(request)

    def stop(self) -> None:
        self._stopping = True

    def _execute(self, request: Request) -> Response:
        """クライアントの cwd に移って既存の main() をそのまま呼ぶ。

        設定ファイルはカレントディレクトリ基準で読まれるため、cwd を合わせることで
        サーバーの起動場所が結果に影響しなくなる（設計 3）。
        """
        stdout = io.StringIO()
        stderr = io.StringIO()
        previous_cwd = os.getcwd()
        moved = _chdir(request.cwd)
        session_module.activate(self.session)
        try:
            with _config_env(request.config_path):
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exit_code = self._executor(list(request.argv))
        except BaseException as exc:  # noqa: BLE001 - サーバーは要求 1 件で落ちない
            return Response(
                stdout=stdout.getvalue(),
                stderr=stderr.getvalue() + f"[ERROR] server failure: {exc}\n",
                exit_code=EXIT_UNEXPECTED,
                instance_id=self.instance_id,
            )
        finally:
            session_module.deactivate()
            if moved:
                _chdir(previous_cwd)
        return Response(
            stdout=stdout.getvalue(),
            stderr=stderr.getvalue(),
            exit_code=exit_code,
            instance_id=self.instance_id,
        )

    def _reject(self, error: str, message: str) -> Response:
        return Response(exit_code=EXIT_UNEXPECTED, error=error, message=message, instance_id=self.instance_id)

    def _write_state(self) -> None:
        if not self._write_state_file:
            return
        write_state(
            ServerState(
                pid=os.getpid(),
                pipe=getattr(self.transport, "name", str(getattr(self.transport, "address", ""))),
                instance_id=self.instance_id,
                version=self.version,
                started_at=now_text(),
                allow_actions=self.allow_actions,
                idle_timeout=int(self.idle_timeout),
            )
        )

    def _clear_state(self) -> None:
        if self._write_state_file:
            clear_state()


def _poll_interval(idle_timeout: float) -> float:
    if idle_timeout <= 0:
        return ACCEPT_POLL_SECONDS
    return min(ACCEPT_POLL_SECONDS, idle_timeout)


def _default_executor(argv: list[str]) -> int:
    from pyselector.cli import main

    return main(argv)


@contextlib.contextmanager
def _config_env(config_path: str | None):
    """設定ファイルの指定をクライアントに合わせる。

    PYSELECTOR_CONFIG はプロセスごとの環境変数なので、送ってもらった値を
    要求のあいだだけ被せる。そうしないとサーバーを起動したときの値が使われてしまう。
    """
    previous = os.environ.get(CONFIG_ENV_VAR)
    if config_path is None:
        os.environ.pop(CONFIG_ENV_VAR, None)
    else:
        os.environ[CONFIG_ENV_VAR] = config_path
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(CONFIG_ENV_VAR, None)
        else:
            os.environ[CONFIG_ENV_VAR] = previous


def _chdir(path: str) -> bool:
    if not path:
        return False
    try:
        os.chdir(path)
    except OSError:
        return False
    return True
