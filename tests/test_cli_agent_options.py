from pathlib import Path

import pytest

from pyselector import cli
from pyselector.install import SKILL_RELATIVE_PATHS


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def default_config(monkeypatch):
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(FIXTURES)


def _capture(monkeypatch, name):
    captured = {}

    def fake_run(args):
        captured["args"] = args
        return 0

    monkeypatch.setattr(cli, name, fake_run)
    return captured


def test_inspect_at_is_parsed_into_a_point(monkeypatch):
    captured = _capture(monkeypatch, "run_inspect")

    result = cli.main(["inspect", "--at", "636,2240"])

    assert result == 0
    assert captured["args"].at == (636, 2240)
    assert captured["args"].handle is None


def test_inspect_at_accepts_spaces_and_negative_coordinates(monkeypatch):
    captured = _capture(monkeypatch, "run_inspect")

    result = cli.main(["inspect", "--at", "-10, 20"])

    assert result == 0
    assert captured["args"].at == (-10, 20)


@pytest.mark.parametrize("value", ["abc", "10", "10,20,30", "10,y"])
def test_inspect_at_rejects_invalid_format(value, capsys):
    result = cli.main(["inspect", "--at", value])

    assert result == 10
    assert "must be in X,Y format" in capsys.readouterr().err


def test_inspect_handle_accepts_hex_and_decimal(monkeypatch):
    captured = _capture(monkeypatch, "run_inspect")
    cli.main(["inspect", "--handle", "0x2E20F46"])
    assert captured["args"].handle == 0x2E20F46

    cli.main(["inspect", "--handle", "48304966"])
    assert captured["args"].handle == 48304966


def test_inspect_handle_rejects_invalid_value(capsys):
    result = cli.main(["inspect", "--handle", "zz"])

    assert result == 10
    assert "must be an integer or a 0x-prefixed hex value" in capsys.readouterr().err


def test_inspect_at_and_handle_are_exclusive(capsys):
    result = cli.main(["inspect", "--at", "1,2", "--handle", "0x10"])

    assert result == 10
    assert "--at, --handle and --ref cannot be used together" in capsys.readouterr().err


@pytest.mark.parametrize("target", [["--at", "1,2"], ["--handle", "0x10"]])
def test_inspect_delay_cannot_be_combined_with_non_interactive_target(target, capsys):
    result = cli.main(["inspect", "--delay", "3", *target])

    assert result == 10
    assert "--delay cannot be used with --at, --handle or --ref" in capsys.readouterr().err


def test_inspect_without_at_keeps_overlay_defaults(monkeypatch):
    captured = _capture(monkeypatch, "run_inspect")

    result = cli.main(["inspect"])

    assert result == 0
    assert captured["args"].at is None
    assert captured["args"].handle is None
    assert captured["args"].delay is None


@pytest.mark.parametrize(
    "argv",
    [
        ["tree"],
        ["tree", "--cursor", "--window-title", "x"],
        ["tree", "--cursor", "--window-handle", "0x10"],
        ["tree", "--window-title", "x", "--window-handle", "0x10"],
    ],
)
def test_tree_requires_exactly_one_target(argv, capsys):
    result = cli.main(argv)

    assert result == 10
    assert "tree requires exactly one of --cursor, --ref, --window-title or --window-handle" in capsys.readouterr().err


def test_tree_accepts_window_handle(monkeypatch):
    captured = _capture(monkeypatch, "run_tree")

    result = cli.main(["tree", "--window-handle", "0x2E20F46"])

    assert result == 0
    assert captured["args"].window_handle == 0x2E20F46
    assert captured["args"].summary is False
    assert captured["args"].compact is False


@pytest.mark.parametrize(
    "argv",
    [
        ["find"],
        ["find", "--at", "1,2", "--window-title", "x"],
        ["find", "--window-title", "x", "--window-handle", "0x10"],
    ],
)
def test_find_requires_exactly_one_target(argv, capsys):
    result = cli.main(argv)

    assert result == 10
    assert "find requires exactly one of --at, --ref, --window-title or --window-handle" in capsys.readouterr().err


def test_find_uses_config_defaults(monkeypatch):
    captured = _capture(monkeypatch, "run_find")

    result = cli.main(["find", "--window-handle", "0x10"])

    args = captured["args"]
    assert result == 0
    assert args.backend == "uia"
    assert args.depth == 8
    assert args.max_items == 200
    assert args.limit == 20
    assert args.selector_limit == 3
    assert args.only_visible is True
    assert args.with_selectors is False
    assert args.selector_evaluation_max_items == 10
    assert args.found_index_trial_count == 3


def test_find_arguments_override_defaults(monkeypatch):
    captured = _capture(monkeypatch, "run_find")

    result = cli.main(
        [
            "find",
            "--window-handle",
            "0x10",
            "--backend",
            "win32",
            "--depth",
            "2",
            "--limit",
            "5",
            "--with-selectors",
            "--selector-limit",
            "1",
            "--include-hidden",
            "--text",
            "保存",
        ]
    )

    args = captured["args"]
    assert result == 0
    assert args.backend == "win32"
    assert args.depth == 2
    assert args.limit == 5
    assert args.with_selectors is True
    assert args.selector_limit == 1
    assert args.only_visible is False
    assert args.text == "保存"


def test_windows_uses_config_defaults(monkeypatch):
    captured = _capture(monkeypatch, "run_windows")

    result = cli.main(["windows"])

    args = captured["args"]
    assert result == 0
    assert args.backend == "win32"
    assert args.max_items == 50
    assert args.only_visible is True
    assert args.include_untitled is False


def test_windows_rejects_conflicting_visibility_options(capsys):
    result = cli.main(["windows", "--only-visible", "--include-hidden"])

    assert result == 10
    assert "--only-visible and --include-hidden cannot be used together" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv,expected_action,expected_value",
    [
        (["act", "--window-handle", "0x10", "--auto-id", "a", "--click"], "click", None),
        (["act", "--window-handle", "0x10", "--auto-id", "a", "--double-click"], "double_click", None),
        (["act", "--window-handle", "0x10", "--auto-id", "a", "--right-click"], "right_click", None),
        (["act", "--window-handle", "0x10", "--auto-id", "a", "--invoke"], "invoke", None),
        (["act", "--window-handle", "0x10", "--auto-id", "a", "--focus"], "focus", None),
        (["act", "--window-handle", "0x10", "--auto-id", "a", "--set-text", "x"], "set_text", "x"),
        (["act", "--window-handle", "0x10", "--auto-id", "a", "--send-keys", "{ENTER}"], "send_keys", "{ENTER}"),
    ],
)
def test_act_resolves_the_requested_action(monkeypatch, argv, expected_action, expected_value):
    captured = _capture(monkeypatch, "run_act")

    result = cli.main(argv)

    assert result == 0
    assert captured["args"].action == expected_action
    assert captured["args"].value == expected_value


def test_act_requires_an_action(capsys):
    result = cli.main(["act", "--window-handle", "0x10", "--auto-id", "a"])

    assert result == 10
    assert "act requires exactly one action" in capsys.readouterr().err


def test_act_rejects_two_actions(capsys):
    result = cli.main(["act", "--window-handle", "0x10", "--auto-id", "a", "--click", "--send-keys", "x"])

    assert result == 10
    assert "act requires exactly one action" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [
        ["act", "--click"],
        ["act", "--at", "1,2", "--window-handle", "0x10", "--click"],
        ["act", "--window-title", "x", "--window-handle", "0x10", "--click"],
    ],
)
def test_act_requires_exactly_one_target(argv, capsys):
    result = cli.main(argv)

    assert result == 10
    assert "act requires exactly one of --at, --ref, --window-title or --window-handle" in capsys.readouterr().err


def test_act_at_cannot_be_combined_with_element_conditions(capsys):
    result = cli.main(["act", "--at", "1,2", "--auto-id", "a", "--click"])

    assert result == 10
    assert "--at selects the target directly" in capsys.readouterr().err


def test_act_defaults_come_from_config(monkeypatch):
    captured = _capture(monkeypatch, "run_act")

    result = cli.main(["act", "--window-handle", "0x10", "--auto-id", "a", "--click"])

    args = captured["args"]
    assert result == 0
    assert args.backend == "uia"
    assert args.depth == 8
    assert args.max_items == 200
    assert args.only_visible is True
    assert args.allow_actions is False
    assert args.dry_run is False
    assert args.diff is False
    assert args.env_allow_actions is False


def test_act_backend_does_not_accept_both(capsys):
    result = cli.main(["act", "--window-handle", "0x10", "--auto-id", "a", "--click", "--backend", "both"])

    assert result == 10
    assert "invalid choice: 'both'" in capsys.readouterr().err


def test_act_passes_the_env_permission_through(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("PYSELECTOR_ALLOW_ACTIONS=true\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    captured = _capture(monkeypatch, "run_act")

    result = cli.main(["act", "--window-handle", "0x10", "--auto-id", "a", "--click", "--allow-actions"])

    assert result == 0
    assert captured["args"].env_allow_actions is True
    assert captured["args"].allow_actions is True


def test_diff_takes_two_paths(monkeypatch, tmp_path):
    captured = _capture(monkeypatch, "run_diff")

    result = cli.main(["diff", str(tmp_path / "a.json"), str(tmp_path / "b.json")])

    assert result == 0
    assert captured["args"].before == tmp_path / "a.json"
    assert captured["args"].after == tmp_path / "b.json"


def test_diff_requires_two_paths(capsys):
    result = cli.main(["diff", "only-one.json"])

    assert result == 10
    assert "arguments are required: after" in capsys.readouterr().err


def test_install_skills_claude_writes_skill_to_current_directory(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    result = cli.main(["install-skills", "--claude"])

    target = tmp_path / SKILL_RELATIVE_PATHS["claude"]
    assert result == 0
    assert target == tmp_path / ".claude" / "skills" / "pyselector-cli" / "SKILL.md"
    assert "name: pyselector-cli" in target.read_text(encoding="utf-8")
    assert "[INFO] Claude Code skill installed:" in capsys.readouterr().out


def test_install_skills_can_write_both_skills(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    result = cli.main(["install-skills", "--copilot", "--claude"])

    assert result == 0
    assert (tmp_path / SKILL_RELATIVE_PATHS["copilot"]).exists()
    assert (tmp_path / SKILL_RELATIVE_PATHS["claude"]).exists()


def test_install_skills_is_not_named_install(capsys):
    result = cli.main(["install", "--copilot"])

    assert result == 10
    assert "invalid choice: 'install'" in capsys.readouterr().err
