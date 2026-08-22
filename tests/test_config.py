from pathlib import Path

import pytest

from pyselector import cli
from pyselector.config import load_config
from pyselector.install import SKILL_CONTENT, SKILL_RELATIVE_PATHS
from pyselector.utils.errors import ArgumentError


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
    assert args.delay is None
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


def test_cli_delay_without_value_uses_five_seconds(monkeypatch):
    captured = {}
    monkeypatch.setenv("PYSELECTOR_CONFIG", str(FIXTURES / "custom_config.json"))

    def fake_run_inspect(args):
        captured["args"] = args
        return 0

    monkeypatch.setattr(cli, "run_inspect", fake_run_inspect)

    result = cli.main(["--delay"])

    args = captured["args"]
    assert result == 0
    assert args.command == "inspect"
    assert args.delay == 5


def test_cli_prints_logo_before_running_command(monkeypatch, capsys):
    monkeypatch.setenv("PYSELECTOR_CONFIG", str(FIXTURES / "custom_config.json"))
    monkeypatch.setattr(cli, "_is_interactive_stdout", lambda: True)
    monkeypatch.setenv("NO_COLOR", "1")

    def fake_run_inspect(args):
        print("INSPECT START")
        return 0

    monkeypatch.setattr(cli, "run_inspect", fake_run_inspect)

    result = cli.main(["inspect"])

    assert result == 0
    logo_lines = cli._LOGO_PATH.read_text(encoding="utf-8").rstrip().splitlines()
    assert capsys.readouterr().out.splitlines()[: len(logo_lines) + 1] == logo_lines + ["INSPECT START"]


def test_cli_suppresses_logo_when_stdout_is_not_a_terminal(monkeypatch, capsys):
    monkeypatch.setenv("PYSELECTOR_CONFIG", str(FIXTURES / "custom_config.json"))
    monkeypatch.setattr(cli, "_is_interactive_stdout", lambda: False)
    monkeypatch.setattr(cli, "run_inspect", lambda args: print("INSPECT START") or 0)

    result = cli.main(["inspect"])

    assert result == 0
    assert capsys.readouterr().out == "INSPECT START\n"


def test_cli_json_suppresses_logo(monkeypatch, capsys):
    captured = {}
    monkeypatch.setenv("PYSELECTOR_CONFIG", str(FIXTURES / "custom_config.json"))

    def fake_run_inspect(args):
        captured["args"] = args
        print("{}")
        return 0

    monkeypatch.setattr(cli, "run_inspect", fake_run_inspect)

    result = cli.main(["inspect", "--json"])

    assert result == 0
    assert captured["args"].json is True
    assert capsys.readouterr().out == "{}\n"


def test_cli_install_skills_copilot_writes_skill_to_current_directory(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)

    result = cli.main(["install-skills", "--copilot"])

    target = tmp_path / SKILL_RELATIVE_PATHS["copilot"]
    assert result == 0
    assert target == tmp_path / ".github" / "skills" / "pyselector-cli" / "SKILL.md"
    assert target.read_text(encoding="utf-8") == SKILL_CONTENT
    assert "name: pyselector-cli" in SKILL_CONTENT
    assert "[INFO] GitHub Copilot skill installed:" in capsys.readouterr().out


def test_cli_install_skills_requires_target(monkeypatch, capsys):
    monkeypatch.setenv("PYSELECTOR_CONFIG", str(FIXTURES / "custom_config.json"))

    result = cli.main(["install-skills"])

    assert result == 10
    assert "install-skills requires --copilot or --claude" in capsys.readouterr().err


def test_default_windows_and_find_config(monkeypatch):
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(FIXTURES)

    config = load_config()

    assert config.windows.backend == "win32"
    assert config.windows.max_items == 50
    assert config.windows.only_visible is True
    assert config.find.backend == "uia"
    assert config.find.scope == "window"
    assert config.find.timeout == 5
    assert config.find.depth == 8
    assert config.find.max_items == 200
    assert config.find.limit == 20
    assert config.find.selector_limit == 3
    assert config.find.only_visible is True


def test_load_config_reads_windows_and_find_sections(monkeypatch, tmp_path):
    config_path = tmp_path / "pyselector_config.json"
    config_path.write_text(
        '{"windows": {"backend": "uia", "max_items": 5}, "find": {"depth": 3, "limit": 2, "selector_limit": 1}}',
        encoding="utf-8",
    )
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)

    config = load_config()

    assert config.windows.backend == "uia"
    assert config.windows.max_items == 5
    assert config.find.depth == 3
    assert config.find.limit == 2
    assert config.find.selector_limit == 1


@pytest.mark.parametrize(
    "raw,message",
    [
        ('{"windows": {"backend": "chrome"}}', "config value must be one of"),
        ('{"windows": {"unknown": 1}}', "unknown config key in windows"),
        ('{"find": {"limit": 0}}', "config value must be a positive integer"),
        ('{"find": {"depth": -1}}', "config value must be a non-negative integer"),
        ('{"find": {"only_visible": "yes"}}', "config value must be true or false"),
    ],
)
def test_load_config_rejects_invalid_agent_sections(monkeypatch, tmp_path, raw, message):
    config_path = tmp_path / "pyselector_config.json"
    config_path.write_text(raw, encoding="utf-8")
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ArgumentError) as error:
        load_config()

    assert message in str(error.value)


def test_logo_gradient_uses_blue_ansi_colors():
    output = cli._format_logo_gradient("py")

    assert output == "\033[38;2;36;210;255mp\033[38;2;106;130;255my\033[0m"


def test_logo_gradient_uses_full_logo_width_for_short_lines():
    output = cli._format_logo_gradient("p       y\n    y")

    assert output.splitlines()[1] == "    \033[38;2;71;170;255my\033[0m"
