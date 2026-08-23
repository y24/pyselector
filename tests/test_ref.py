import json
from pathlib import Path

import pytest

from pyselector import cli
from pyselector.backends.common import LOCAL_INSTANCE_ID, is_wrapper_alive
from pyselector.backends.uia_inspector import UiaInspector
from pyselector.model.element_info import ElementInfo
from pyselector.output.json_output import format_find_results_json
from pyselector.model.find_result import FindMatch, FindResult
from pyselector.server import session as session_module
from pyselector.server.refs import RefRegistry, parse_ref, ref_backend
from pyselector.server.session import ServerSession
from pyselector.utils.errors import EXIT_STALE_REF, StaleRefError


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def default_config(monkeypatch):
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(FIXTURES)


class FakeWrapper:
    """pywinauto wrapper の代役。生存確認だけ本物と同じ形で答える。"""

    def __init__(self, name="Save", alive=True, handle=None):
        self.name = name
        self.alive = alive
        self._handle = handle

    def is_visible(self):
        if not self.alive:
            raise RuntimeError("element is gone")
        return True

    def window_text(self):
        return self.name

    def class_name(self):
        return "Button"

    def handle(self):
        return self._handle

    def children(self):
        return []


@pytest.fixture
def session():
    session = ServerSession("7f3a2b", max_refs=5000, allow_actions=True)
    session_module.activate(session)
    try:
        yield session
    finally:
        session_module.deactivate()


# --- ref の形式 ----------------------------------------------------------


def test_a_ref_carries_the_backend_the_instance_and_a_serial():
    registry = RefRegistry("7f3a2b")

    assert registry.issue("uia", FakeWrapper()) == "uia:7f3a2b:1"
    assert registry.issue("uia", FakeWrapper()) == "uia:7f3a2b:2"


def test_the_serial_is_shared_across_backends():
    """1 つの表を backend で共有するので、ref はサーバー全体で一意になる。"""
    registry = RefRegistry("7f3a2b")

    assert registry.issue("uia", FakeWrapper()) == "uia:7f3a2b:1"
    assert registry.issue("win32", FakeWrapper()) == "win32:7f3a2b:2"


def test_a_ref_is_parsed_back_into_its_parts():
    assert parse_ref("uia:7f3a2b:42") == ("uia", "7f3a2b", 42)


def test_a_ref_names_its_own_backend():
    assert ref_backend("win32:7f3a2b:42") == "win32"


@pytest.mark.parametrize(
    "ref",
    ["", "garbage", "uia:7f3a2b", "uia:7f3a2b:42:9", "mshtml:7f3a2b:42", "uia::42", "uia:7f3a2b:x"],
)
def test_a_malformed_ref_is_stale_without_consulting_the_table(ref):
    with pytest.raises(StaleRefError):
        parse_ref(ref)


# --- 世代管理と LRU ------------------------------------------------------


def test_a_ref_from_another_instance_is_not_found():
    """サーバーを再起動すると、インスタンス ID が変わって古い ref は引けなくなる。"""
    registry = RefRegistry("7f3a2b")
    ref = registry.issue("uia", FakeWrapper())
    restarted = RefRegistry("c0ffee")

    assert restarted.get(ref) is None
    with pytest.raises(StaleRefError):
        restarted.resolve(ref)


def test_the_oldest_refs_are_evicted_once_the_table_is_full():
    registry = RefRegistry("7f3a2b", max_refs=2)
    first = registry.issue("uia", FakeWrapper())
    second = registry.issue("uia", FakeWrapper())
    third = registry.issue("uia", FakeWrapper())

    assert registry.get(first) is None
    assert registry.get(second) is not None
    assert registry.get(third) is not None


def test_an_evicted_ref_is_stale():
    registry = RefRegistry("7f3a2b", max_refs=1)
    first = registry.issue("uia", FakeWrapper())
    registry.issue("uia", FakeWrapper())

    with pytest.raises(StaleRefError):
        registry.resolve(first)


def test_using_a_ref_keeps_it_from_being_evicted_first():
    registry = RefRegistry("7f3a2b", max_refs=2)
    first = registry.issue("uia", FakeWrapper())
    second = registry.issue("uia", FakeWrapper())
    registry.get(first)
    registry.issue("uia", FakeWrapper())

    assert registry.get(first) is not None
    assert registry.get(second) is None


def test_the_handle_map_is_bounded_like_the_ref_table(session):
    """常駐プロセスでは handle の逆引き表も増え続けるので、同じ上限で抑える。"""
    inspector = session.inspector("uia", lambda backend: UiaInspector())
    inspector.use_ref_registry(RefRegistry("7f3a2b", max_refs=2))
    for handle in range(5):
        inspector._track(FakeWrapper(handle=handle), ElementInfo(backend="uia", handle=handle))

    assert len(inspector._wrapper_by_handle) == 2
    assert set(inspector._wrapper_by_handle) == {3, 4}


def test_the_local_handle_map_is_not_evicted():
    inspector = UiaInspector()
    for handle in range(50):
        inspector._track(FakeWrapper(handle=handle), ElementInfo(backend="uia", handle=handle))

    assert len(inspector._wrapper_by_handle) == 50


def test_the_local_registry_has_no_ceiling():
    """1 コマンドで終わるローカル実行では追い出さない。走査の途中で自分の ref を失う。"""
    inspector = UiaInspector()

    assert inspector._refs.max_refs is None
    assert inspector._refs.instance_id == LOCAL_INSTANCE_ID


# --- 生存確認 ------------------------------------------------------------


def test_a_live_wrapper_passes_the_check():
    assert is_wrapper_alive(FakeWrapper(alive=True)) is True


def test_a_dead_wrapper_fails_the_check():
    assert is_wrapper_alive(FakeWrapper(alive=False)) is False


def test_a_wrapper_without_a_visibility_check_is_treated_as_live():
    """判定できないことを失効の根拠にはしない。"""

    class Bare:
        pass

    assert is_wrapper_alive(Bare()) is True


def test_element_from_ref_returns_the_same_element(session):
    inspector = session.inspector("uia", lambda backend: UiaInspector())
    ref = inspector._refs.issue("uia", FakeWrapper(name="保存"))

    element = inspector.element_from_ref(ref)

    assert element.ref == ref
    assert element.window_text == "保存"


def test_element_from_ref_refuses_a_dead_wrapper(session):
    inspector = session.inspector("uia", lambda backend: UiaInspector())
    ref = inspector._refs.issue("uia", FakeWrapper(alive=False))

    with pytest.raises(StaleRefError):
        inspector.element_from_ref(ref)


def test_element_from_ref_refuses_an_unknown_ref(session):
    inspector = session.inspector("uia", lambda backend: UiaInspector())

    with pytest.raises(StaleRefError):
        inspector.element_from_ref("uia:7f3a2b:999")


# --- セッションが inspector を使い回すこと ------------------------------


def test_the_session_reuses_the_inspector_so_refs_survive(session):
    created = []

    def factory(backend):
        created.append(backend)
        return UiaInspector()

    first = session.inspector("uia", factory)
    second = session.inspector("uia", factory)

    assert first is second
    assert created == ["uia"]


def test_the_session_registry_is_shared_by_every_backend(session):
    from pyselector.backends.win32_inspector import Win32Inspector

    uia = session.inspector("uia", lambda backend: UiaInspector())
    win32 = session.inspector("win32", lambda backend: Win32Inspector())

    assert uia._refs is win32._refs is session.refs


# --- 出力に載る条件 ------------------------------------------------------


def _find_results():
    element = ElementInfo(backend="uia", window_text="Save", ref="uia:7f3a2b:42")
    return [FindResult(backend="uia", root=None, matches=[FindMatch(element=element)])]


def test_local_execution_does_not_publish_refs():
    """ローカルの ref はプロセス終了とともに消えるので出さない（設計 7.2）。"""
    payload = json.loads(format_find_results_json(_find_results()))

    assert payload["served"] is False
    assert "ref" not in payload["results"][0]["matches"][0]["element"]


def test_a_served_response_publishes_refs(session):
    payload = json.loads(format_find_results_json(_find_results()))

    assert payload["served"] is True
    assert payload["results"][0]["matches"][0]["element"]["ref"] == "uia:7f3a2b:42"


def test_refs_survive_the_compact_output(session):
    payload = json.loads(format_find_results_json(_find_results(), compact=True))

    assert payload["results"][0]["matches"][0]["element"]["ref"] == "uia:7f3a2b:42"


# --- CLI ------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["inspect", "--json", "--ref", "uia:7f3a2b:1", "--at", "1,2"],
        ["tree", "--json", "--ref", "uia:7f3a2b:1", "--window-handle", "0x10"],
        ["find", "--json", "--ref", "uia:7f3a2b:1", "--window-handle", "0x10"],
        ["act", "--json", "--ref", "uia:7f3a2b:1", "--window-handle", "0x10", "--click"],
    ],
)
def test_ref_cannot_be_combined_with_another_target(argv):
    assert cli.main(argv) == 10


def test_a_ref_chooses_the_backend_it_names(monkeypatch):
    captured = {}
    monkeypatch.setattr(cli, "run_find", lambda args: captured.update(vars(args)) or 0)

    cli.main(["find", "--json", "--ref", "win32:7f3a2b:1", "--server", "off"])

    assert captured["ref"] == "win32:7f3a2b:1"


def test_a_stale_ref_reports_its_own_exit_code(capsys):
    exit_code = cli.main(["find", "--json", "--ref", "uia:7f3a2b:1", "--server", "off"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == EXIT_STALE_REF
    assert payload["error"]["code"] == "stale_ref"


def test_act_does_not_touch_anything_when_the_ref_is_stale(monkeypatch, tmp_path, capsys):
    """失効した ref では、操作の前に止まる（設計 7.4）。"""
    config = tmp_path / "pyselector_config.json"
    config.write_text(json.dumps({"act": {"allow_actions": True}}), encoding="utf-8")
    monkeypatch.setenv("PYSELECTOR_CONFIG", str(config))
    performed = []
    monkeypatch.setattr(
        "pyselector.actions.perform_action",
        lambda *args, **kwargs: performed.append(args) or "click",
    )

    exit_code = cli.main(
        ["act", "--json", "--ref", "uia:7f3a2b:1", "--click", "--allow-actions", "--server", "off"]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == EXIT_STALE_REF
    assert payload["error"]["code"] == "stale_ref"
    assert performed == []
