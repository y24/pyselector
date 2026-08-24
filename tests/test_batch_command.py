import io
import json
from argparse import Namespace

import pytest

from pyselector.commands import batch as batch_command
from pyselector.utils.errors import ArgumentError


@pytest.fixture
def fake_main(monkeypatch):
    """cli.main を差し替え、ステップの実行を記録する。"""
    calls = []
    plan = {}

    def main(argv):
        calls.append(list(argv))
        command = argv[0]
        exit_code = plan.get(command, 0)
        print(json.dumps({"command": command, "status": "success" if exit_code == 0 else "error"}))
        return exit_code

    import pyselector.cli

    monkeypatch.setattr(pyselector.cli, "main", main)
    return Namespace(calls=calls, plan=plan)


def _steps_file(tmp_path, steps):
    path = tmp_path / "steps.json"
    path.write_text(json.dumps({"steps": steps}), encoding="utf-8")
    return str(path)


def _args(steps, **overrides):
    values = dict(command="batch", steps=steps, continue_on_error=False, json=True)
    values.update(overrides)
    return Namespace(**values)


def _run(capsys, args):
    exit_code = batch_command.run_batch(args)
    return exit_code, json.loads(capsys.readouterr().out)


def test_every_step_runs_in_order(tmp_path, capsys, fake_main):
    steps = _steps_file(
        tmp_path,
        [
            {"command": "windows", "args": ["--compact"]},
            {"command": "find", "args": ["--window-handle", "0x10"]},
        ],
    )

    exit_code, payload = _run(capsys, _args(steps))

    assert exit_code == 0
    assert payload["completed"] == 2
    assert [call[0] for call in fake_main.calls] == ["windows", "find"]


def test_json_is_forced_on_every_step(tmp_path, capsys, fake_main):
    steps = _steps_file(tmp_path, [{"command": "windows", "args": []}])

    _run(capsys, _args(steps))

    assert fake_main.calls[0] == ["windows", "--json"]


def test_an_explicit_json_flag_is_not_duplicated(tmp_path, capsys, fake_main):
    steps = _steps_file(tmp_path, [{"command": "windows", "args": ["--json"]}])

    _run(capsys, _args(steps))

    assert fake_main.calls[0].count("--json") == 1


def test_the_first_failure_stops_the_run(tmp_path, capsys, fake_main):
    fake_main.plan["expect"] = 12
    steps = _steps_file(
        tmp_path,
        [
            {"command": "windows", "args": []},
            {"command": "expect", "args": ["--exists"]},
            {"command": "find", "args": []},
        ],
    )

    exit_code, payload = _run(capsys, _args(steps))

    assert exit_code == 12
    assert payload["completed"] == 2
    assert payload["failed_exit_code"] == 12
    assert [call[0] for call in fake_main.calls] == ["windows", "expect"]


def test_continue_on_error_runs_everything(tmp_path, capsys, fake_main):
    fake_main.plan["expect"] = 12
    steps = _steps_file(
        tmp_path,
        [
            {"command": "expect", "args": []},
            {"command": "find", "args": []},
        ],
    )

    exit_code, payload = _run(capsys, _args(steps, continue_on_error=True))

    assert exit_code == 12
    assert payload["completed"] == 2


def test_each_step_carries_its_envelope(tmp_path, capsys, fake_main):
    steps = _steps_file(tmp_path, [{"command": "windows", "args": []}])

    _, payload = _run(capsys, _args(steps))

    assert payload["steps"][0]["result"]["command"] == "windows"
    assert payload["steps"][0]["output"] is None


def test_output_that_is_not_json_is_kept(tmp_path, capsys, monkeypatch):
    import pyselector.cli

    monkeypatch.setattr(pyselector.cli, "main", lambda argv: print("plain text") or 0)
    steps = _steps_file(tmp_path, [{"command": "windows", "args": []}])

    _, payload = _run(capsys, _args(steps))

    assert payload["steps"][0]["result"] is None
    assert "plain text" in payload["steps"][0]["output"]


def test_batch_cannot_nest(tmp_path, capsys, fake_main):
    steps = _steps_file(tmp_path, [{"command": "batch", "args": ["other.json"]}])

    with pytest.raises(ArgumentError, match="batch"):
        batch_command.run_batch(_args(steps))


def test_serve_is_not_allowed_as_a_step(tmp_path, capsys, fake_main):
    steps = _steps_file(tmp_path, [{"command": "serve", "args": []}])

    with pytest.raises(ArgumentError):
        batch_command.run_batch(_args(steps))


def test_a_step_without_a_command_is_rejected(tmp_path, capsys, fake_main):
    steps = _steps_file(tmp_path, [{"args": ["--json"]}])

    with pytest.raises(ArgumentError, match="command"):
        batch_command.run_batch(_args(steps))


def test_non_string_args_are_rejected(tmp_path, capsys, fake_main):
    steps = _steps_file(tmp_path, [{"command": "find", "args": [1, 2]}])

    with pytest.raises(ArgumentError, match="args"):
        batch_command.run_batch(_args(steps))


def test_an_empty_steps_array_is_rejected(tmp_path, capsys, fake_main):
    steps = _steps_file(tmp_path, [])

    with pytest.raises(ArgumentError, match="steps"):
        batch_command.run_batch(_args(steps))


def test_broken_json_is_reported_with_its_origin(tmp_path, capsys, fake_main):
    path = tmp_path / "steps.json"
    path.write_text("{ not json", encoding="utf-8")

    with pytest.raises(ArgumentError, match="steps.json"):
        batch_command.run_batch(_args(str(path)))


def test_a_bare_array_is_accepted(tmp_path, capsys, fake_main):
    path = tmp_path / "steps.json"
    path.write_text(json.dumps([{"command": "windows", "args": []}]), encoding="utf-8")

    exit_code, payload = _run(capsys, _args(str(path)))

    assert exit_code == 0
    assert payload["completed"] == 1


def test_steps_can_come_from_standard_input(monkeypatch, capsys, fake_main):
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps({"steps": [{"command": "windows", "args": []}]}))
    )

    exit_code, payload = _run(capsys, _args("-"))

    assert exit_code == 0
    assert payload["completed"] == 1
