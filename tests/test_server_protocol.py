import json
from pathlib import Path

import pytest

from pyselector import __version__, cli
from pyselector.server.protocol import (
    ERROR_COMMAND_NOT_ALLOWED,
    ERROR_MALFORMED_REQUEST,
    ERROR_PROTOCOL_MISMATCH,
    ERROR_VERSION_MISMATCH,
    PROTOCOL_VERSION,
    ProtocolError,
    Request,
    Response,
    command_of,
    decode_request,
    decode_response,
    encode_request,
    encode_response,
)
from tests.server_helpers import echo_executor, running_server


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def default_config(monkeypatch):
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(FIXTURES)


def test_request_survives_a_round_trip():
    request = Request(argv=["find", "--json"], cwd="D:\\work", version="0.2.0")

    restored = decode_request(encode_request(request))

    assert restored == request


def test_response_survives_a_round_trip():
    response = Response(stdout="out", stderr="err", exit_code=3, instance_id="7f3a2b")

    assert decode_response(encode_response(response)) == response


def test_non_ascii_arguments_survive_the_wire():
    request = Request(argv=["find", "--text", "電卓"], cwd="D:\\作業")

    assert decode_request(encode_request(request)).argv == ["find", "--text", "電卓"]


@pytest.mark.parametrize(
    "payload",
    [b"not json", b"[]", b'{"argv": "find"}', b'{"argv": [1]}', b'{"protocol": "1"}'],
)
def test_malformed_messages_are_rejected(payload):
    with pytest.raises(ProtocolError):
        decode_request(payload)


@pytest.mark.parametrize(
    "argv, expected",
    [
        (["find", "--json"], "find"),
        (["--at", "1,2"], "inspect"),
        ([], None),
    ],
)
def test_command_is_read_from_the_front_of_argv(argv, expected):
    assert command_of(argv) == expected


def test_argv_reaches_the_server_untouched(tmp_path):
    recorder = []
    with running_server(executor=echo_executor(recorder)) as server:
        response = server.request(["find", "--json", "--text", "保存"], tmp_path)

    assert response.exit_code == 0
    assert recorder[0]["argv"] == ["find", "--json", "--text", "保存"]
    assert response.stdout == "find --json --text 保存\n"


def test_the_server_runs_the_request_in_the_client_cwd(tmp_path):
    recorder = []
    with running_server(executor=echo_executor(recorder)) as server:
        server.request(["version"], tmp_path)

    assert Path(recorder[0]["cwd"]).resolve() == tmp_path.resolve()


def test_served_output_matches_local_execution(tmp_path):
    """同じ argv ならサーバー経由でもローカルでも同じ出力・同じ終了コードになる。

    served だけは意図した差分なので、比較の前に揃える（設計 6.3）。
    """
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(json.dumps(_tree_payload("Save")), encoding="utf-8")
    after.write_text(json.dumps(_tree_payload("Saved")), encoding="utf-8")
    argv = ["diff", "before.json", "after.json", "--json"]

    with running_server() as server:
        response = server.request(argv, tmp_path)

    local_exit, local_stdout = _run_locally(argv, tmp_path)

    assert response.exit_code == local_exit
    assert _without_served(response.stdout) == _without_served(local_stdout)


def test_only_the_served_flag_differs_between_the_two_paths(tmp_path):
    argv = ["version", "--json"]

    with running_server() as server:
        response = server.request(argv, tmp_path)
    _, local_stdout = _run_locally(argv, tmp_path)

    assert json.loads(response.stdout)["served"] is True
    assert json.loads(local_stdout)["served"] is False


@pytest.mark.parametrize("command", ["serve", "install-skills"])
def test_commands_outside_the_allowlist_are_refused(command, tmp_path):
    recorder = []
    with running_server(executor=echo_executor(recorder)) as server:
        response = server.request([command, "--claude"], tmp_path)

    assert response.error == ERROR_COMMAND_NOT_ALLOWED
    assert recorder == []


def test_a_different_client_version_is_refused(tmp_path):
    recorder = []
    with running_server(executor=echo_executor(recorder)) as server:
        response = server.request(["find", "--json"], tmp_path, version="9.9.9")

    assert response.error == ERROR_VERSION_MISMATCH
    assert __version__ in response.message
    assert recorder == []


def test_a_different_protocol_version_is_refused(tmp_path):
    with running_server() as server:
        response = server.send(Request(argv=["version"], cwd=str(tmp_path), protocol=PROTOCOL_VERSION + 1))

    assert response.error == ERROR_PROTOCOL_MISMATCH


def test_a_malformed_message_does_not_stop_the_server(tmp_path):
    with running_server() as server:
        connection = server.client()._connect(5.0)
        try:
            connection.send(b"not json at all")
            broken = decode_response(connection.receive())
        finally:
            connection.close()
        following = server.request(["version", "--json"], tmp_path)

    assert broken.error == ERROR_MALFORMED_REQUEST
    assert following.exit_code == 0


def test_an_unexpected_failure_inside_the_command_becomes_one_response(tmp_path):
    def explode(argv):
        raise RuntimeError("boom")

    with running_server(executor=explode) as server:
        response = server.request(["version"], tmp_path)
        following = server.request(["version"], tmp_path)

    assert response.exit_code == 100
    assert "boom" in response.stderr
    assert following.exit_code == 100


def _tree_payload(text):
    node = {
        "depth": 1,
        "window_text": text,
        "control_type": "Button",
        "automation_id": "saveBtn",
        "class_name": "Button",
        "friendly_class_name": "Button",
        "control_id": None,
        "handle": None,
        "rectangle": None,
    }
    return {
        "schema_version": 2,
        "command": "tree",
        "status": "success",
        "results": [
            {
                "backend": "uia",
                "status": "success",
                "message": None,
                "root": None,
                "reached_limit": False,
                "nodes": [node],
            }
        ],
    }


def _run_locally(argv, cwd):
    import contextlib
    import io
    import os

    previous = os.getcwd()
    os.chdir(cwd)
    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            exit_code = cli.main(list(argv))
    finally:
        os.chdir(previous)
    return exit_code, stdout.getvalue()


def _without_served(text):
    payload = json.loads(text)
    payload.pop("served", None)
    return payload
