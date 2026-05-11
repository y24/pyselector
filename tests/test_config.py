from pathlib import Path

from pyselector import cli
from pyselector.config import load_config


FIXTURES = Path(__file__).parent / "fixtures"


def test_load_config_reads_values_from_env_path(monkeypatch):
    monkeypatch.setenv("PYSELECTOR_CONFIG", str(FIXTURES / "custom_config.json"))
    config = load_config()

    assert config.inspect.delay == 2
    assert config.inspect.timeout == 9
    assert config.inspect.backend == "uia"
    assert config.inspect.scope == "desktop"
    assert config.inspect.only_visible is False
    assert config.tree.depth == 4
    assert config.selector.evaluation_max_items == 7
    assert config.selector.found_index_trial_count == 4
    assert config.loaded_path == FIXTURES / "custom_config.json"


def test_load_config_reads_pyselector_config_from_current_directory(monkeypatch, tmp_path):
    config_path = tmp_path / "pyselector_config.json"
    config_path.write_text('{"inspect": {"delay": 1}}', encoding="utf-8")
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)

    config = load_config()

    assert config.inspect.delay == 1
    assert config.loaded_path == config_path


def test_default_tree_backend_is_both(monkeypatch):
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(FIXTURES)

    config = load_config()

    assert config.tree.backend == "both"


def test_default_tree_max_items_is_50(monkeypatch):
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(FIXTURES)

    config = load_config()

    assert config.tree.max_items == 50


def test_cli_uses_config_defaults_for_inspect(monkeypatch):
    captured = {}
    monkeypatch.setenv("PYSELECTOR_CONFIG", str(FIXTURES / "custom_config.json"))

    def fake_run_inspect(args):
        captured["args"] = args
        return 0

    monkeypatch.setattr(cli, "run_inspect", fake_run_inspect)

    result = cli.main(["inspect"])

    args = captured["args"]
    assert result == 0
    assert args.delay == 2
    assert args.timeout == 9
    assert args.backend == "uia"
    assert args.scope == "desktop"
    assert args.only_visible is False
    assert args.selector_evaluation_max_items == 7
    assert args.found_index_trial_count == 4
    assert args.config_path == FIXTURES / "custom_config.json"


def test_cli_arguments_override_config(monkeypatch):
    captured = {}
    monkeypatch.setenv("PYSELECTOR_CONFIG", str(FIXTURES / "custom_config.json"))

    def fake_run_inspect(args):
        captured["args"] = args
        return 0

    monkeypatch.setattr(cli, "run_inspect", fake_run_inspect)

    result = cli.main(["inspect", "--delay", "0", "--timeout", "3", "--include-hidden"])

    args = captured["args"]
    assert result == 0
    assert args.delay == 0
    assert args.timeout == 3
    assert args.only_visible is False
