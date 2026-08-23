import json
from pathlib import Path

import pytest

from pyselector.utils.errors import EXIT_ACTION_NOT_ALLOWED, EXIT_STALE_REF
from tests.server_helpers import running_server


FIXTURES = Path(__file__).parent / "fixtures"
STALE_REF = "uia:deadbe:9999"


@pytest.fixture(autouse=True)
def default_config(monkeypatch):
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(FIXTURES)


def _workspace(tmp_path, allow_actions):
    """クライアント側の cwd。.env はここから読まれる。"""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".env").write_text(
        f"PYSELECTOR_ALLOW_ACTIONS={'true' if allow_actions else 'false'}\n", encoding="utf-8"
    )
    return tmp_path


def _act(server, cwd, ref=STALE_REF):
    return server.request(["act", "--json", "--ref", ref, "--click", "--allow-actions"], cwd)


def _error(response):
    return json.loads(response.stdout)["error"]


def test_a_manually_started_server_refuses_act_by_default(tmp_path):
    """手動起動は明示的な opt-in。読み取り専用のデーモンを選べるようにする。"""
    cwd = _workspace(tmp_path, allow_actions=True)

    with running_server(allow_actions=False) as server:
        response = _act(server, cwd)

    assert response.exit_code == EXIT_ACTION_NOT_ALLOWED
    assert _error(response)["code"] == "action_not_allowed"
    assert "serve --allow-actions" in _error(response)["message"]
    assert "serve --stop" in _error(response)["message"]


def test_the_refusal_happens_before_the_target_is_even_resolved(tmp_path):
    """許可されていないサーバーは、要素を探しにいく前に断る。"""
    cwd = _workspace(tmp_path, allow_actions=True)

    with running_server(allow_actions=False) as server:
        response = _act(server, cwd)

    assert _error(response)["code"] == "action_not_allowed"


def test_the_env_permission_is_reported_before_the_daemon_ceiling(tmp_path):
    """.env を書いていないだけの利用者に、デーモンの話を返さない。"""
    cwd = _workspace(tmp_path, allow_actions=False)

    with running_server(allow_actions=False) as server:
        response = _act(server, cwd)

    assert response.exit_code == EXIT_ACTION_NOT_ALLOWED
    assert "PYSELECTOR_ALLOW_ACTIONS" in _error(response)["message"]
    assert "serve" not in _error(response)["message"]


def test_an_allowed_server_gets_as_far_as_resolving_the_target(tmp_path):
    """--allow-actions で起動すれば act は通り、次の関門は ref の生存確認になる。"""
    cwd = _workspace(tmp_path, allow_actions=True)

    with running_server(allow_actions=True) as server:
        response = _act(server, cwd)

    assert response.exit_code == EXIT_STALE_REF
    assert _error(response)["code"] == "stale_ref"


def test_the_env_gate_is_read_from_the_client_cwd(tmp_path):
    """.env の PYSELECTOR_ALLOW_ACTIONS はクライアントの cwd で評価される（設計 8.2）。"""
    refusing = _workspace(tmp_path / "refusing", allow_actions=False)
    allowing = _workspace(tmp_path / "allowing", allow_actions=True)

    with running_server(allow_actions=True) as server:
        refused = _act(server, refusing)
        allowed = _act(server, allowing)

    assert refused.exit_code == EXIT_ACTION_NOT_ALLOWED
    assert "PYSELECTOR_ALLOW_ACTIONS" in _error(refused)["message"]
    assert allowed.exit_code == EXIT_STALE_REF


def test_the_command_flag_is_still_required(tmp_path):
    cwd = _workspace(tmp_path, allow_actions=True)

    with running_server(allow_actions=True) as server:
        response = server.request(["act", "--json", "--ref", STALE_REF, "--click"], cwd)

    assert response.exit_code == EXIT_ACTION_NOT_ALLOWED
    assert "--allow-actions" in _error(response)["message"]


def test_a_dry_run_is_allowed_even_on_a_refusing_server(tmp_path):
    """何も操作しないので、常駐の同意とは無関係に通す。止まるのは ref の生存確認。"""
    cwd = _workspace(tmp_path, allow_actions=False)

    with running_server(allow_actions=False) as server:
        response = server.request(["act", "--json", "--ref", STALE_REF, "--click", "--dry-run"], cwd)

    assert response.exit_code == EXIT_STALE_REF


def test_other_commands_are_unaffected_by_the_act_gate(tmp_path):
    cwd = _workspace(tmp_path, allow_actions=False)

    with running_server(allow_actions=False) as server:
        response = server.request(["version", "--json"], cwd)

    assert response.exit_code == 0
