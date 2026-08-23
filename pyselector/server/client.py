from __future__ import annotations

import os
import subprocess
import sys
from argparse import Namespace
from dataclasses import dataclass
from typing import Any, Callable

from pyselector import __version__
from pyselector.config import CONFIG_ENV_VAR
from pyselector.server import session as session_module
from pyselector.server.protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    Request,
    Response,
    SERVER_COMMANDS,
    decode_response,
    encode_request,
)

SERVER_MODES = ("auto", "off", "require")

#: 対話的に対象を選ぶコマンドはサーバーに送らない。
#: オーバーラップしたオーバーレイやカウントダウンを常駐プロセス側で開いても、
#: 応答を一括で返すこの経路では体験が壊れるため（設計 6.2）。
_INTERACTIVE_REASON = "対話的に対象を選ぶ実行はサーバーを経由しません"


@dataclass(frozen=True)
class ServerDecision:
    """サーバーを使うかどうかの判断結果。"""

    use_server: bool
    reason: str = ""


def resolve_mode(explicit: str | None, enabled: bool) -> str:
    """``--server`` の指定と設定から実効モードを決める。

    明示指定が最優先。書かれていなければ ``server.enabled`` が既定を決める。
    設定を書かない限り ``off`` なので、クライアントはサーバーを探しにいかない。
    """
    if explicit is not None:
        return explicit
    return "auto" if enabled else "off"


def decide(mode: str, args: Namespace, json_output: bool) -> ServerDecision:
    """このコマンドをサーバーに投げてよいかを判断する。"""
    if session_module.is_serving():
        # サーバー内で実行中。ここから更にサーバーへ投げると再帰する。
        return ServerDecision(False, "already running inside the server")
    if mode == "off":
        return ServerDecision(False, "--server off")
    command = getattr(args, "command", None) or "inspect"
    if command not in SERVER_COMMANDS:
        return ServerDecision(False, f"サーバーで実行しないコマンドです: {command}")
    if _is_interactive(command, args):
        return ServerDecision(False, _INTERACTIVE_REASON)
    if mode == "require":
        return ServerDecision(True, "--server require")
    if not json_output:
        # テキスト出力は進捗ログが逐次表示されることに意味がある（設計 6.2）。
        return ServerDecision(False, "--json 指定時のみサーバーを使います")
    return ServerDecision(True, "--server auto")


def _is_interactive(command: str, args: Namespace) -> bool:
    if command == "inspect":
        has_target = getattr(args, "at", None) is not None or getattr(args, "handle", None) is not None
        has_target = has_target or getattr(args, "ref", None) is not None
        return not has_target or getattr(args, "delay", None) is not None
    if command == "tree":
        return bool(getattr(args, "cursor", False))
    return False


class ServerClient:
    """常駐サーバーへの 1 往復。

    繋がらなければ ``None`` を返し、呼び出し側がローカル実行に落ちる。
    """

    def __init__(
        self,
        connect: Callable[[float], Any] | None = None,
        version: str = __version__,
    ) -> None:
        self._connect = connect or _connect_named_pipe
        self.version = version

    def request(self, argv: list[str], cwd: str, timeout: float) -> Response | None:
        request = Request(
            argv=list(argv),
            cwd=cwd,
            version=self.version,
            protocol=PROTOCOL_VERSION,
            config_path=os.environ.get(CONFIG_ENV_VAR),
        )
        return self.send(request, timeout)

    def send(self, request: Request, timeout: float) -> Response | None:
        try:
            connection = self._connect(timeout)
        except Exception:
            return None
        try:
            connection.send(encode_request(request))
            payload = connection.receive()
        except Exception:
            return None
        finally:
            connection.close()
        try:
            return decode_response(payload)
        except ProtocolError:
            return None


def _connect_named_pipe(timeout: float):
    from pyselector.server.pipe import connect_pipe, pipe_name_for_current_user

    return connect_pipe(pipe_name_for_current_user(), timeout)


def start_server_detached(idle_timeout: int | None = None, allow_actions: bool = False) -> bool:
    """サーバーをデタッチして起動する。

    起動を待たずに戻る。1 回目のコマンドは呼び出し側がローカル実行で返すため
    体感が悪化しない（設計 5.2）。

    ``allow_actions`` には、その設定ファイルが act を許可しているかを渡す。
    手動起動は明示的な opt-in、自動起動は設定に書かれた同意の引き継ぎ、という対称にする。
    設定そのものは要求ごとにクライアントの cwd で評価され続けるので、この上限が
    許可を広げることはなく、狭める方向にしか働かない。
    """
    command = [sys.executable, "-m", "pyselector", "serve"]
    if idle_timeout is not None:
        command += ["--idle-timeout", str(idle_timeout)]
    if allow_actions:
        command.append("--allow-actions")
    creationflags = 0
    for name in ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP", "CREATE_NO_WINDOW"):
        creationflags |= getattr(subprocess, name, 0)
    try:
        subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            cwd=os.getcwd(),
            creationflags=creationflags,
        )
    except OSError:
        return False
    return True
