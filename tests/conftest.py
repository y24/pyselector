from pathlib import Path


def pytest_configure(config):
    cache_dir = config.getini("cache_dir")
    if cache_dir:
        Path(cache_dir, "v", "cache").mkdir(parents=True, exist_ok=True)
