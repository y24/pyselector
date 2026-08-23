import json
from argparse import Namespace
from pathlib import Path

import pytest

from pyselector import cli
from pyselector.server import client as server_client
from pyselector.server import session as session_module
from pyselector.server.protocol import ERROR_VERSION_MISMATCH, Response
from pyselector.utils.errors import EXIT_SERVER_UNAVAILABLE


FIXTURES = Path(__file__).parent / "fixtures"
#: never_really_start_a_server が差し替える前の本物。起動の組み立て方そのものを見るテストで使う。
REAL_START_SERVER_DETACHED = server_client.start_server_detached
SERVER_ENABLED = {"server": {"enabled": True}}
SERVER_ENABLED_NO_AUTO_START = {"server": {"enabled": True, "auto_start": False}}


@pytest.fixture(autouse=True)
def default_config(monkeypatch):
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(FIXTURES)


@pytest.fixture(autouse=True)
def never_really_start_a_server(monkeypatch):
    started = []

    def fake_start(idle_timeout=None, allow_actions=False):
        started.append({"idle_timeout": idle_timeout, "allow_actions": allow_actions})
        return True

    monkeypatch.setattr(server_client, "start_server_detached", fake_start)
    return started


def _config_file(tmp_path, monkeypatch, payload):
    path = tmp_path / "pyselector_config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("PYSELECTOR_CONFIG", str(path))
    return path


def _spy_client(monkeypatch, response):
    """ServerClient を差し替えて、送られた要求を記録する。"""
    sent = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, argv, cwd, timeout):
            sent.append({"argv": list(argv), "cwd": cwd, "timeout": timeout})
            return response

    monkeypatch.setattr(server_client, "ServerClient", FakeClient)
    return sent


def _stub_runner(monkeypatch, name="run_find"):
    calls = []
    monkeypatch.setattr(cli, name, lambda args: calls.append(args) or 0)
    return calls


def test_the_cli_offers_exactly_the_modes_the_client_knows():
    """cli は起動コストのために SERVER_MODES を自前で持つ。値がずれないよう固定する。"""
    assert cli.SERVER_MODES == server_client.SERVER_MODES


# --- resolve_mode -------------------------------------------------------


@pytest.mark.parametrize(
    "explicit, enabled, expected",
    [
        (None, False, "off"),
        (None, True, "auto"),
        ("off", True, "off"),
        ("auto", False, "auto"),
        ("require", False, "require"),
    ],
)
def test_the_effective_mode_comes_from_the_flag_then_the_config(explicit, enabled, expected):
    assert server_client.resolve_mode(explicit, enabled) == expected


# --- decide -------------------------------------------------------------


def test_off_never_looks_for_a_server():
    args = Namespace(command="find", at=None)

    assert server_client.decide("off", args, json_output=True).use_server is False


def test_auto_uses_the_server_for_json_output():
    args = Namespace(command="find", at=None)

    assert server_client.decide("auto", args, json_output=True).use_server is True


def test_auto_stays_local_for_text_output():
    """テキスト出力は進捗ログが逐次表示されることに意味がある（設計 6.2）。"""
    args = Namespace(command="find", at=None)

    assert server_client.decide("auto", args, json_output=False).use_server is False


def test_require_uses_the_server_even_for_text_output():
    args = Namespace(command="find", at=None)

    assert server_client.decide("require", args, json_output=False).use_server is True


@pytest.mark.parametrize("command", ["install-skills", "serve"])
def test_commands_outside_the_allowlist_stay_local(command):
    args = Namespace(command=command)

    assert server_client.decide("auto", args, json_output=True).use_server is False


def test_inspect_without_a_target_stays_local():
    """オーバーレイで座標を選ぶ実行は、常駐プロセス側で開いても意味がない。"""
    args = Namespace(command="inspect", at=None, handle=None, ref=None, delay=None)

    assert server_client.decide("auto", args, json_output=True).use_server is False


def test_inspect_with_a_coordinate_uses_the_server():
    args = Namespace(command="inspect", at=(10, 20), handle=None, ref=None, delay=None)

    assert server_client.decide("auto", args, json_output=True).use_server is True


def test_inspect_with_a_countdown_stays_local():
    args = Namespace(command="inspect", at=None, handle=100, ref=None, delay=5)

    assert server_client.decide("auto", args, json_output=True).use_server is False


def test_tree_with_cursor_stays_local():
    args = Namespace(command="tree", cursor=True, ref=None)

    assert server_client.decide("auto", args, json_output=True).use_server is False


def test_a_request_already_running_inside_the_server_is_not_forwarded_again(monkeypatch):
    """サーバー内の実行が更にサーバーへ投げると再帰する。"""
    session = session_module.ServerSession("7f3a2b")
    session_module.activate(session)
    try:
        args = Namespace(command="find", at=None)
        assert server_client.decide("require", args, json_output=True).use_server is False
    finally:
        session_module.deactivate()


# --- start_server_detached ----------------------------------------------


def _spy_popen(monkeypatch):
    calls = []

    class FakePopen:
        def __init__(self, command, **kwargs):
            calls.append({"command": list(command), "kwargs": kwargs})

    monkeypatch.setattr("subprocess.Popen", FakePopen)
    return calls


def test_the_detached_server_is_started_through_the_package_entry_point(monkeypatch):
    calls = _spy_popen(monkeypatch)

    assert REAL_START_SERVER_DETACHED(300) is True
    assert calls[0]["command"][1:] == ["-m", "pyselector", "serve", "--idle-timeout", "300"]


def test_the_detached_server_receives_the_act_consent(monkeypatch):
    calls = _spy_popen(monkeypatch)

    REAL_START_SERVER_DETACHED(300, allow_actions=True)

    assert "--allow-actions" in calls[0]["command"]


def test_the_detached_server_is_started_without_act_by_default(monkeypatch):
    calls = _spy_popen(monkeypatch)

    REAL_START_SERVER_DETACHED(300)

    assert "--allow-actions" not in calls[0]["command"]


def test_a_failure_to_spawn_is_reported_rather_than_raised(monkeypatch):
    def explode(*args, **kwargs):
        raise OSError("no such executable")

    monkeypatch.setattr("subprocess.Popen", explode)

    assert REAL_START_SERVER_DETACHED(300) is False


# --- main() の経路 -------------------------------------------------------


def test_server_off_does_not_look_for_a_server(monkeypatch, tmp_path):
    _config_file(tmp_path, monkeypatch, SERVER_ENABLED)
    sent = _spy_client(monkeypatch, None)
    calls = _stub_runner(monkeypatch)

    assert cli.main(["find", "--json", "--window-handle", "0x10", "--server", "off"]) == 0
    assert sent == []
    assert len(calls) == 1


def test_the_default_config_does_not_look_for_a_server(monkeypatch):
    sent = _spy_client(monkeypatch, None)
    calls = _stub_runner(monkeypatch)

    assert cli.main(["find", "--json", "--window-handle", "0x10"]) == 0
    assert sent == []
    assert len(calls) == 1


def test_enabling_the_server_in_the_config_makes_auto_the_default(monkeypatch, tmp_path):
    _config_file(tmp_path, monkeypatch, SERVER_ENABLED)
    sent = _spy_client(monkeypatch, Response(stdout="{}\n", exit_code=0))
    calls = _stub_runner(monkeypatch)

    assert cli.main(["find", "--json", "--window-handle", "0x10"]) == 0
    assert len(sent) == 1
    assert calls == []


def test_the_server_response_is_passed_through_unchanged(monkeypatch, tmp_path, capsys):
    _config_file(tmp_path, monkeypatch, SERVER_ENABLED)
    _spy_client(monkeypatch, Response(stdout="payload\n", stderr="note\n", exit_code=5))
    _stub_runner(monkeypatch)

    exit_code = cli.main(["find", "--json", "--window-handle", "0x10"])
    captured = capsys.readouterr()

    assert exit_code == 5
    assert captured.out == "payload\n"
    assert captured.err == "note\n"


def test_the_whole_argv_is_forwarded(monkeypatch, tmp_path):
    _config_file(tmp_path, monkeypatch, SERVER_ENABLED)
    sent = _spy_client(monkeypatch, Response(exit_code=0))
    _stub_runner(monkeypatch)

    cli.main(["find", "--json", "--window-handle", "0x10", "--control-type", "Button"])

    assert sent[0]["argv"] == ["find", "--json", "--window-handle", "0x10", "--control-type", "Button"]


def test_auto_falls_back_to_local_execution_when_nothing_answers(monkeypatch, tmp_path):
    _config_file(tmp_path, monkeypatch, SERVER_ENABLED_NO_AUTO_START)
    _spy_client(monkeypatch, None)
    calls = _stub_runner(monkeypatch)

    assert cli.main(["find", "--json", "--window-handle", "0x10"]) == 0
    assert len(calls) == 1


def test_auto_start_happens_once_the_connection_fails(monkeypatch, tmp_path, never_really_start_a_server):
    _config_file(tmp_path, monkeypatch, SERVER_ENABLED)
    _spy_client(monkeypatch, None)
    calls = _stub_runner(monkeypatch)

    assert cli.main(["find", "--json", "--window-handle", "0x10"]) == 0
    # 起動は待たない。この 1 回はローカルで返す（設計 5.2）。
    assert len(never_really_start_a_server) == 1
    assert len(calls) == 1


def test_auto_start_inherits_the_act_consent_from_the_config(monkeypatch, tmp_path, never_really_start_a_server):
    """設定で act を許した利用者に、更に手動起動まで求めない。"""
    _config_file(tmp_path, monkeypatch, {"server": {"enabled": True}, "act": {"allow_actions": True}})
    _spy_client(monkeypatch, None)
    _stub_runner(monkeypatch)

    cli.main(["find", "--json", "--window-handle", "0x10"])

    assert never_really_start_a_server[0]["allow_actions"] is True


def test_auto_start_does_not_grant_act_the_config_withholds(monkeypatch, tmp_path, never_really_start_a_server):
    _config_file(tmp_path, monkeypatch, {"server": {"enabled": True}, "act": {"allow_actions": False}})
    _spy_client(monkeypatch, None)
    _stub_runner(monkeypatch)

    cli.main(["find", "--json", "--window-handle", "0x10"])

    assert never_really_start_a_server[0]["allow_actions"] is False


def test_auto_start_passes_the_configured_idle_timeout(monkeypatch, tmp_path, never_really_start_a_server):
    _config_file(tmp_path, monkeypatch, {"server": {"enabled": True, "idle_timeout": 600}})
    _spy_client(monkeypatch, None)
    _stub_runner(monkeypatch)

    cli.main(["find", "--json", "--window-handle", "0x10"])

    assert never_really_start_a_server[0]["idle_timeout"] == 600


def test_auto_start_is_skipped_when_the_user_manages_the_process(monkeypatch, tmp_path, never_really_start_a_server):
    _config_file(tmp_path, monkeypatch, SERVER_ENABLED_NO_AUTO_START)
    _spy_client(monkeypatch, None)
    _stub_runner(monkeypatch)

    cli.main(["find", "--json", "--window-handle", "0x10"])

    assert never_really_start_a_server == []


def test_require_fails_with_its_own_exit_code_when_nothing_answers(monkeypatch, capsys):
    _spy_client(monkeypatch, None)
    calls = _stub_runner(monkeypatch)

    exit_code = cli.main(["find", "--json", "--window-handle", "0x10", "--server", "require"])
    captured = capsys.readouterr()

    assert exit_code == EXIT_SERVER_UNAVAILABLE
    assert calls == []
    assert json.loads(captured.out)["error"]["code"] == "server_unavailable"


def test_require_inside_the_server_runs_the_command_instead_of_failing(tmp_path):
    """--server require は argv ごと転送される。サーバー側で再評価して失敗してはいけない。"""
    from tests.server_helpers import running_server

    with running_server() as server:
        response = server.request(["version", "--json", "--server", "require"], tmp_path)

    assert response.exit_code == 0
    assert json.loads(response.stdout)["served"] is True


def test_require_fails_when_the_command_cannot_be_served(monkeypatch, capsys):
    calls = _stub_runner(monkeypatch, "run_inspect")

    exit_code = cli.main(["inspect", "--json", "--server", "require"])

    assert exit_code == EXIT_SERVER_UNAVAILABLE
    assert calls == []


def test_a_version_mismatch_falls_back_and_says_so(monkeypatch, tmp_path, capsys):
    _config_file(tmp_path, monkeypatch, SERVER_ENABLED)
    _spy_client(
        monkeypatch,
        Response(exit_code=100, error=ERROR_VERSION_MISMATCH, message="版数が違います"),
    )
    calls = _stub_runner(monkeypatch)

    exit_code = cli.main(["find", "--json", "--window-handle", "0x10"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert len(calls) == 1
    assert "版数が違います" in captured.err


def test_require_does_not_fall_back_on_a_rejected_request(monkeypatch, tmp_path):
    _config_file(tmp_path, monkeypatch, SERVER_ENABLED)
    _spy_client(
        monkeypatch,
        Response(exit_code=100, error=ERROR_VERSION_MISMATCH, message="版数が違います"),
    )
    calls = _stub_runner(monkeypatch)

    assert cli.main(["find", "--json", "--window-handle", "0x10", "--server", "require"]) == EXIT_SERVER_UNAVAILABLE
    assert calls == []


def test_the_connect_timeout_comes_from_the_config(monkeypatch, tmp_path):
    _config_file(tmp_path, monkeypatch, {"server": {"enabled": True, "connect_timeout": 7}})
    sent = _spy_client(monkeypatch, Response(exit_code=0))
    _stub_runner(monkeypatch)

    cli.main(["find", "--json", "--window-handle", "0x10"])

    assert sent[0]["timeout"] == 7
