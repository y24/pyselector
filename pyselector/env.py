"""`.env` からの UI 操作の許可を読む。

UI 操作の許可だけは `pyselector_config.json` ではなく `.env` に置く。設定ファイルは
リポジトリと一緒に配布されるが、`.env` は配布されない。許可をそちらに移すことで、
リポジトリを受け取っただけの環境が UI を操作できる状態にはならない。

`.env` ファイルはカレントディレクトリから探す。設定ファイルと同じ基準なので、常駐
モードでもクライアントの cwd で判定される。
"""

from __future__ import annotations

import os
from pathlib import Path

from pyselector.utils.errors import ArgumentError


ENV_FILE_NAME = ".env"
ALLOW_ACTIONS_VAR = "PYSELECTOR_ALLOW_ACTIONS"

_TRUE_VALUES = {"true", "1", "yes", "on"}
_FALSE_VALUES = {"false", "0", "no", "off", ""}


def load_allow_actions() -> bool:
    """UI 操作が許可されているかを返す。既定は無効。"""
    value = read_env_value(ALLOW_ACTIONS_VAR)
    if value is None:
        return False
    return _as_bool(value, ALLOW_ACTIONS_VAR)


def read_env_value(name: str) -> str | None:
    """`.env` を優先し、無ければプロセスの環境変数を見る。

    `.env` を優先するのは、許可の所在をファイル 1 つに寄せるため。シェルに古い値が
    残っていても、手元の `.env` に書いた内容がそのまま効く。
    """
    values = read_env_file(Path.cwd() / ENV_FILE_NAME)
    if name in values:
        return values[name]
    return os.environ.get(name)


def read_env_file(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ArgumentError(f"cannot read env file: {path}: {exc}") from exc
    values: dict[str, str] = {}
    for line in text.splitlines():
        entry = _parse_line(line)
        if entry is not None:
            values[entry[0]] = entry[1]
    return values


def _parse_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].lstrip()
    key, _, value = stripped.partition("=")
    key = key.strip()
    if not key:
        return None
    return key, _unquote(value.strip())


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _as_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ArgumentError(f"{name} must be true or false: {value}")
