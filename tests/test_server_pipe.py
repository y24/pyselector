"""実パイプを使う結合テスト。

サーバーのロジックはループバック TCP 側で検証済みなので、ここは名前付きパイプの
実装そのもの（往復と ACL）だけを見る（設計 12）。
"""

import json
import os
import threading
import uuid

import pytest

from pyselector import __version__
from pyselector.server.client import ServerClient
from pyselector.server.protocol import CONTROL_STOP, Request
from pyselector.server.server import Server

pipe = pytest.importorskip("pyselector.server.pipe")
pytest.importorskip("win32pipe")

PIPE_POLL_SECONDS = 0.05
CONNECT_TIMEOUT = 20.0


@pytest.fixture
def pipe_server():
    """テスト専用の名前で実パイプのサーバーを立てる。

    実運用の名前（SID そのまま）を使うと、開発機で動いている常駐サーバーと
    ぶつかるため、名前を一意にする。
    """
    name = f"{pipe.PIPE_NAME_PREFIX}test-{uuid.uuid4().hex}"
    transport = pipe.NamedPipeTransport(name=name)
    # 受付スレッドを起こす前にパイプを作っておく。存在する前に繋ぎにいく競合を避ける。
    transport.listen()
    server = Server(transport, idle_timeout=60, write_state_file=False)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_seconds": PIPE_POLL_SECONDS}, daemon=True)
    thread.start()
    client = ServerClient(connect=lambda timeout: pipe.connect_pipe(name, timeout))
    try:
        yield name, client
    finally:
        client.send(Request(control=CONTROL_STOP, version=__version__), CONNECT_TIMEOUT)
        thread.join(timeout=10)


def test_a_request_makes_the_round_trip_over_a_real_pipe(pipe_server):
    _, client = pipe_server

    response = client.request(["version", "--json"], os.getcwd(), CONNECT_TIMEOUT)

    assert response is not None
    assert response.exit_code == 0
    assert json.loads(response.stdout)["served"] is True


def test_a_message_larger_than_one_read_survives(pipe_server):
    """メッセージモードの読み切り（ERROR_MORE_DATA のループ）を通す。"""
    _, client = pipe_server
    padding = "あ" * 200_000

    response = client.request(["version", "--json", "--unknown-" + padding], os.getcwd(), CONNECT_TIMEOUT)

    assert response is not None
    assert response.exit_code != 0


def test_several_requests_reuse_the_same_pipe_name(pipe_server):
    _, client = pipe_server

    codes = [client.request(["version", "--json"], os.getcwd(), CONNECT_TIMEOUT).exit_code for _ in range(3)]

    assert codes == [0, 0, 0]


def test_connecting_to_a_name_nobody_serves_fails_rather_than_hanging():
    name = f"{pipe.PIPE_NAME_PREFIX}absent-{uuid.uuid4().hex}"

    with pytest.raises(pipe.PipeUnavailableError):
        pipe.connect_pipe(name, 0.2)


def test_the_client_returns_nothing_when_the_pipe_is_absent():
    name = f"{pipe.PIPE_NAME_PREFIX}absent-{uuid.uuid4().hex}"
    client = ServerClient(connect=lambda timeout: pipe.connect_pipe(name, timeout))

    assert client.request(["version", "--json"], os.getcwd(), 0.2) is None


def test_the_pipe_name_is_derived_from_the_current_user_sid():
    name = pipe.pipe_name_for_current_user()

    assert name.startswith(pipe.PIPE_NAME_PREFIX)
    assert name[len(pipe.PIPE_NAME_PREFIX) :].startswith("S-1-")


def test_the_acl_only_admits_the_running_user_and_system():
    """パイプに渡す ACL が、実行ユーザーと SYSTEM 以外を一切含まないこと（設計 4.2）。"""
    import win32con
    import win32security

    attributes = pipe._security_attributes(pipe._win32())
    dacl = attributes.SECURITY_DESCRIPTOR.GetSecurityDescriptorDacl()
    aces = [dacl.GetAce(index) for index in range(dacl.GetAceCount())]
    granted = {win32security.ConvertSidToStringSid(ace[2]): ace[1] for ace in aces}

    assert set(granted) == {pipe.current_user_sid(), pipe.LOCAL_SYSTEM_SID}
    assert all(mask == win32con.GENERIC_ALL for mask in granted.values())
    assert all(ace[0][0] == win32security.ACCESS_ALLOWED_ACE_TYPE for ace in aces)


def test_the_acl_does_not_admit_everyone():
    """Everyone / Authenticated Users が紛れ込んでいないことを名指しで確かめる。"""
    import win32security

    attributes = pipe._security_attributes(pipe._win32())
    dacl = attributes.SECURITY_DESCRIPTOR.GetSecurityDescriptorDacl()
    granted = {
        win32security.ConvertSidToStringSid(dacl.GetAce(index)[2]) for index in range(dacl.GetAceCount())
    }

    everyone = "S-1-1-0"
    authenticated_users = "S-1-5-11"
    assert everyone not in granted
    assert authenticated_users not in granted
