from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


PROTOCOL_VERSION = 1

#: サーバーで実行してよいコマンド（設計 8.3 の許可リスト）。
#: ``serve`` は再帰を防ぐため、``install-skills`` はファイルを書き出すため除く。
SERVER_COMMANDS = frozenset({"inspect", "tree", "windows", "find", "expect", "act", "diff", "version"})

#: サーバーが要求そのものを拒んだときの理由。いずれもクライアント側で
#: ローカル実行にフォールバックする。
ERROR_VERSION_MISMATCH = "version_mismatch"
ERROR_PROTOCOL_MISMATCH = "protocol_mismatch"
ERROR_COMMAND_NOT_ALLOWED = "command_not_allowed"
ERROR_MALFORMED_REQUEST = "malformed_request"

CONTROL_STOP = "stop"
CONTROL_PING = "ping"


class ProtocolError(Exception):
    """要求・応答を解釈できなかった。"""


@dataclass(frozen=True)
class Request:
    argv: list[str] = field(default_factory=list)
    cwd: str = ""
    version: str = ""
    protocol: int = PROTOCOL_VERSION
    control: str | None = None
    #: クライアント側の PYSELECTOR_CONFIG。設定の読まれ方をクライアントに合わせるため、
    #: cwd と同じ理由で送る。環境変数はプロセスごとなので、送らないとサーバー側の値が使われてしまう。
    config_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "protocol": self.protocol,
            "version": self.version,
            "cwd": self.cwd,
            "argv": list(self.argv),
        }
        if self.control is not None:
            payload["control"] = self.control
        if self.config_path is not None:
            payload["config_path"] = self.config_path
        return payload


@dataclass(frozen=True)
class Response:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    error: str | None = None
    message: str | None = None
    instance_id: str | None = None

    @property
    def rejected(self) -> bool:
        """サーバーがコマンドを実行せずに突き返したか。"""
        return self.error is not None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
        }
        if self.error is not None:
            payload["error"] = self.error
        if self.message is not None:
            payload["message"] = self.message
        if self.instance_id is not None:
            payload["instance_id"] = self.instance_id
        return payload


def encode_request(request: Request) -> bytes:
    return _encode(request.to_dict())


def decode_request(payload: bytes) -> Request:
    raw = _decode(payload)
    argv = raw.get("argv", [])
    if not isinstance(argv, list) or any(not isinstance(item, str) for item in argv):
        raise ProtocolError("argv must be a list of strings")
    control = raw.get("control")
    if control is not None and not isinstance(control, str):
        raise ProtocolError("control must be a string")
    config_path = raw.get("config_path")
    if config_path is not None and not isinstance(config_path, str):
        raise ProtocolError("config_path must be a string")
    return Request(
        argv=list(argv),
        cwd=_text(raw, "cwd"),
        version=_text(raw, "version"),
        protocol=_int(raw, "protocol", PROTOCOL_VERSION),
        control=control,
        config_path=config_path,
    )


def encode_response(response: Response) -> bytes:
    return _encode(response.to_dict())


def decode_response(payload: bytes) -> Response:
    raw = _decode(payload)
    return Response(
        stdout=_text(raw, "stdout"),
        stderr=_text(raw, "stderr"),
        exit_code=_int(raw, "exit_code", 0),
        error=raw.get("error"),
        message=raw.get("message"),
        instance_id=raw.get("instance_id"),
    )


def command_of(argv: list[str]) -> str | None:
    """argv の先頭からサブコマンド名を取り出す。

    ``main()`` と同じく、オプションで始まる場合は ``inspect`` の暗黙指定とみなす。
    """
    for item in argv:
        if not item.startswith("-"):
            return item
        return "inspect"
    return None


def _encode(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _decode(payload: bytes) -> dict[str, Any]:
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(str(exc)) from exc
    if not isinstance(raw, dict):
        raise ProtocolError("message root must be an object")
    return raw


def _text(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key, "")
    if not isinstance(value, str):
        raise ProtocolError(f"{key} must be a string")
    return value


def _int(raw: dict[str, Any], key: str, default: int) -> int:
    value = raw.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProtocolError(f"{key} must be an integer")
    return value
