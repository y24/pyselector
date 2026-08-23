from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyselector.utils.errors import ArgumentError


CONFIG_FILE_NAME = "pyselector_config.json"
CONFIG_ENV_VAR = "PYSELECTOR_CONFIG"


@dataclass(frozen=True)
class InspectConfig:
    delay: int = 5
    timeout: int = 5
    backend: str = "both"
    scope: str = "window"
    max_items: int | None = None
    only_visible: bool = True


@dataclass(frozen=True)
class TreeConfig:
    delay: int = 5
    backend: str = "both"
    depth: int = 3
    max_items: int = 50
    only_visible: bool = True


@dataclass(frozen=True)
class WindowsConfig:
    backend: str = "win32"
    max_items: int = 50
    only_visible: bool = True


@dataclass(frozen=True)
class FindConfig:
    backend: str = "uia"
    scope: str = "window"
    timeout: int = 5
    depth: int = 8
    max_items: int = 200
    limit: int = 20
    selector_limit: int = 3
    only_visible: bool = True


@dataclass(frozen=True)
class ActConfig:
    # UI 操作は既定で無効。設定と --allow-actions の両方で明示的に有効化する。
    allow_actions: bool = False
    backend: str = "uia"
    depth: int = 8
    max_items: int = 200
    only_visible: bool = True


@dataclass(frozen=True)
class ServerConfig:
    """常駐モードの設定。

    enabled が既定で false なので、設定を書かない限りクライアントはサーバーを
    探しにいかない。既存利用者の挙動は変わらない（設計 9）。
    """

    enabled: bool = False
    auto_start: bool = True
    idle_timeout: int = 300
    max_refs: int = 5000
    connect_timeout: int = 30


@dataclass(frozen=True)
class SelectorConfig:
    evaluation_max_items: int = 10
    found_index_trial_count: int = 3


@dataclass(frozen=True)
class AppConfig:
    inspect: InspectConfig = InspectConfig()
    tree: TreeConfig = TreeConfig()
    windows: WindowsConfig = WindowsConfig()
    find: FindConfig = FindConfig()
    act: ActConfig = ActConfig()
    selector: SelectorConfig = SelectorConfig()
    server: ServerConfig = ServerConfig()
    loaded_path: Path | None = None


def load_config() -> AppConfig:
    path = _resolve_config_path()
    if path is None:
        return AppConfig()
    try:
        with path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
    except json.JSONDecodeError as exc:
        raise ArgumentError(f"invalid config JSON: {path}: {exc}") from exc
    except OSError as exc:
        raise ArgumentError(f"cannot read config file: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ArgumentError(f"config root must be an object: {path}")
    return _build_config(raw, path)


def _resolve_config_path() -> Path | None:
    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        return Path(env_path)
    cwd_path = Path.cwd() / CONFIG_FILE_NAME
    return cwd_path if cwd_path.exists() else None


def _build_config(raw: dict[str, Any], path: Path) -> AppConfig:
    allowed_sections = {"inspect", "tree", "windows", "find", "act", "selector", "server"}
    _reject_unknown_keys(raw, allowed_sections, "config", path)
    inspect = _section(raw, "inspect", path)
    tree = _section(raw, "tree", path)
    windows = _section(raw, "windows", path)
    find = _section(raw, "find", path)
    act = _section(raw, "act", path)
    selector = _section(raw, "selector", path)
    server = _section(raw, "server", path)
    return AppConfig(
        inspect=InspectConfig(
            delay=_non_negative_int(inspect, "delay", 5, path),
            timeout=_positive_int(inspect, "timeout", 5, path),
            backend=_choice(inspect, "backend", "both", {"win32", "uia", "both"}, path),
            scope=_choice(inspect, "scope", "window", {"window", "desktop"}, path),
            max_items=_optional_positive_int(inspect, "max_items", None, path),
            only_visible=_bool(inspect, "only_visible", True, path),
        ),
        tree=TreeConfig(
            delay=_non_negative_int(tree, "delay", 5, path),
            backend=_choice(tree, "backend", "both", {"win32", "uia", "both"}, path),
            depth=_non_negative_int(tree, "depth", 3, path),
            max_items=_positive_int(tree, "max_items", 50, path),
            only_visible=_bool(tree, "only_visible", True, path),
        ),
        windows=WindowsConfig(
            backend=_choice(windows, "backend", "win32", {"win32", "uia", "both"}, path),
            max_items=_positive_int(windows, "max_items", 50, path),
            only_visible=_bool(windows, "only_visible", True, path),
        ),
        find=FindConfig(
            backend=_choice(find, "backend", "uia", {"win32", "uia", "both"}, path),
            scope=_choice(find, "scope", "window", {"window", "desktop"}, path),
            timeout=_positive_int(find, "timeout", 5, path),
            depth=_non_negative_int(find, "depth", 8, path),
            max_items=_positive_int(find, "max_items", 200, path),
            limit=_positive_int(find, "limit", 20, path),
            selector_limit=_positive_int(find, "selector_limit", 3, path),
            only_visible=_bool(find, "only_visible", True, path),
        ),
        act=ActConfig(
            allow_actions=_bool(act, "allow_actions", False, path),
            backend=_choice(act, "backend", "uia", {"win32", "uia"}, path),
            depth=_non_negative_int(act, "depth", 8, path),
            max_items=_positive_int(act, "max_items", 200, path),
            only_visible=_bool(act, "only_visible", True, path),
        ),
        selector=SelectorConfig(
            evaluation_max_items=_positive_int(selector, "evaluation_max_items", 10, path),
            found_index_trial_count=_positive_int(selector, "found_index_trial_count", 3, path),
        ),
        server=ServerConfig(
            enabled=_bool(server, "enabled", False, path),
            auto_start=_bool(server, "auto_start", True, path),
            idle_timeout=_non_negative_int(server, "idle_timeout", 300, path),
            max_refs=_positive_int(server, "max_refs", 5000, path),
            connect_timeout=_positive_int(server, "connect_timeout", 30, path),
        ),
        loaded_path=path,
    )


def _section(raw: dict[str, Any], key: str, path: Path) -> dict[str, Any]:
    value = raw.get(key, {})
    if not isinstance(value, dict):
        raise ArgumentError(f"config section must be an object: {key}: {path}")
    if key == "inspect":
        allowed = {"delay", "timeout", "backend", "scope", "max_items", "only_visible"}
    elif key == "tree":
        allowed = {"delay", "backend", "depth", "max_items", "only_visible"}
    elif key == "windows":
        allowed = {"backend", "max_items", "only_visible"}
    elif key == "find":
        allowed = {"backend", "scope", "timeout", "depth", "max_items", "limit", "selector_limit", "only_visible"}
    elif key == "act":
        allowed = {"allow_actions", "backend", "depth", "max_items", "only_visible"}
    elif key == "server":
        allowed = {"enabled", "auto_start", "idle_timeout", "max_refs", "connect_timeout"}
    else:
        allowed = {"evaluation_max_items", "found_index_trial_count"}
    _reject_unknown_keys(value, allowed, key, path)
    return value


def _reject_unknown_keys(raw: dict[str, Any], allowed: set[str], section: str, path: Path) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ArgumentError(f"unknown config key in {section}: {', '.join(unknown)}: {path}")


def _non_negative_int(raw: dict[str, Any], key: str, default: int, path: Path) -> int:
    value = raw.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ArgumentError(f"config value must be a non-negative integer: {key}: {path}")
    return value


def _positive_int(raw: dict[str, Any], key: str, default: int, path: Path) -> int:
    value = raw.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ArgumentError(f"config value must be a positive integer: {key}: {path}")
    return value


def _optional_positive_int(raw: dict[str, Any], key: str, default: int | None, path: Path) -> int | None:
    value = raw.get(key, default)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ArgumentError(f"config value must be null or a positive integer: {key}: {path}")
    return value


def _choice(raw: dict[str, Any], key: str, default: str, choices: set[str], path: Path) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str) or value not in choices:
        raise ArgumentError(f"config value must be one of {', '.join(sorted(choices))}: {key}: {path}")
    return value


def _bool(raw: dict[str, Any], key: str, default: bool, path: Path) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ArgumentError(f"config value must be true or false: {key}: {path}")
    return value
