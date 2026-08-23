from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_ui_action_permission(monkeypatch):
    """開発者のシェルに残った許可がテスト結果を左右しないようにする。"""
    monkeypatch.delenv("PYSELECTOR_ALLOW_ACTIONS", raising=False)


def pytest_configure(config):
    cache_dir = config.getini("cache_dir")
    if cache_dir:
        Path(cache_dir, "v", "cache").mkdir(parents=True, exist_ok=True)
