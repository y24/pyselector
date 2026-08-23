import json
import os
import threading

import pytest

from pyselector import __version__
from pyselector.server import state as state_module
from pyselector.server.loopback import LoopbackTransport
from pyselector.server.protocol import CONTROL_STOP, Request
from pyselector.server.server import Server
from pyselector.server.state import ServerState, clear_state, read_live_state, read_state, write_state
from tests.server_helpers import POLL_SECONDS, RunningServer, running_server


@pytest.fixture(autouse=True)
def isolated_state_dir(tmp_path, monkeypatch):
    """実ユーザーの %LOCALAPPDATA% を汚さない。"""
    monkeypatch.setenv(state_module.STATE_DIR_ENV_VAR, str(tmp_path / "state"))


def _state(pid=4242, **overrides):
    values = dict(
        pid=pid,
        pipe="\\\\.\\pipe\\pyselector-S-1-5-21-1",
        instance_id="7f3a2b",
        version=__version__,
        started_at="2026-08-23T12:00:00",
        allow_actions=False,
        idle_timeout=300,
    )
    values.update(overrides)
    return ServerState(**values)


def test_state_is_written_and_read_back():
    write_state(_state())

    assert read_state() == _state()


def test_a_missing_state_file_reads_as_nothing():
    assert read_state() is None


def test_a_corrupt_state_file_reads_as_nothing():
    path = state_module.state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json", encoding="utf-8")

    assert read_state() is None


def test_the_running_process_is_reported_as_live():
    write_state(_state(pid=os.getpid()))

    assert read_live_state() is not None


def test_a_dead_pid_clears_the_stale_state_file(monkeypatch):
    write_state(_state(pid=999_999))
    monkeypatch.setattr(state_module, "is_process_alive", lambda pid: False)

    assert read_live_state() is None
    assert not state_module.state_path().exists()


def test_clear_state_is_quiet_when_there_is_nothing_to_clear():
    clear_state()

    assert read_state() is None


def test_the_server_writes_and_removes_its_state_file():
    transport = LoopbackTransport()
    server = Server(transport, idle_timeout=1, clock=_stepping_clock([0.0, 5.0]))

    seen = {}
    original_accept = transport.accept

    def accept(timeout):
        seen["state"] = read_state()
        return original_accept(timeout)

    transport.accept = accept
    server.serve_forever(poll_seconds=0.01)

    assert seen["state"] is not None
    assert seen["state"].instance_id == server.instance_id
    assert read_state() is None


def test_the_server_stops_itself_once_it_has_been_idle(monkeypatch):
    """時計を注入して、アイドル時間だけで終了することを見る。"""
    transport = LoopbackTransport()
    clock = _stepping_clock([0.0, 100.0, 400.0])
    server = Server(transport, idle_timeout=300, clock=clock, write_state_file=False)

    server.serve_forever(poll_seconds=0.01)

    assert server.handled_requests == 0


def test_a_request_pushes_the_idle_deadline_back():
    """要求が来ているあいだは、アイドルタイムアウトに達しない。"""
    with running_server(idle_timeout=300) as server:
        for _ in range(3):
            assert server.request(["version", "--json"], os.getcwd()).exit_code == 0

        assert server.server.handled_requests == 3


def test_idle_timeout_zero_keeps_the_server_running():
    with running_server(idle_timeout=0) as server:
        assert server.request(["version"], os.getcwd()).exit_code == 0


def test_the_stop_control_ends_the_accept_loop():
    transport = LoopbackTransport()
    transport.listen()
    server = Server(transport, idle_timeout=300, write_state_file=False)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_seconds": POLL_SECONDS}, daemon=True)
    thread.start()
    running = RunningServer(server, transport.address)

    response = running.send(Request(control=CONTROL_STOP, version=__version__))
    thread.join(timeout=5)

    assert response.exit_code == 0
    assert not thread.is_alive()


def test_an_unknown_control_is_refused():
    with running_server() as server:
        response = server.send(Request(control="explode", version=__version__))

    assert response.rejected


def _stepping_clock(values):
    """呼ばれるたびに次の時刻を返す時計。使い切ったら最後の値を返し続ける。"""
    remaining = list(values)

    def clock():
        if len(remaining) > 1:
            return remaining.pop(0)
        return remaining[0]

    return clock
