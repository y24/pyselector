from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyselector.utils.errors import ArgumentError


CONFIG_FILE_NAME = "config.json"
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
    backend: str = "win32"
    depth: int = 3
    max_items: int = 200
    only_visible: bool = True


@dataclass(frozen=True)
class SelectorConfig:
    evaluation_max_items: int = 10
    found_index_trial_count: int = 3


@dataclass(frozen=True)
class AppConfig:
    inspect: InspectConfig = InspectConfig()
    tree: TreeConfig = TreeConfig()
    selector: SelectorConfig = SelectorConfig()
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
    allowed_sections = {"inspect", "tree", "selector"}
    _reject_unknown_keys(raw, allowed_sections, "config", path)
    inspect = _section(raw, "inspect", path)
    tree = _section(raw, "tree", path)
    selector = _section(raw, "selector", path)
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
            backend=_choice(tree, "backend", "win32", {"win32", "uia"}, path),
            depth=_non_negative_int(tree, "depth", 3, path),
            max_items=_positive_int(tree, "max_items", 200, path),
            only_visible=_bool(tree, "only_visible", True, path),
        ),
        selector=SelectorConfig(
            evaluation_max_items=_positive_int(selector, "evaluation_max_items", 10, path),
            found_index_trial_count=_positive_int(selector, "found_index_trial_count", 3, path),
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
