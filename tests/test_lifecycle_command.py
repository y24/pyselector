import json
from argparse import Namespace

import pytest

from pyselector.commands import common as command_common
from pyselector.commands import lifecycle
from pyselector.config import load_config
from pyselector.model.element_info import ElementInfo
from pyselector.model.target_window import TargetWindowInfo
from pyselector.record import store
from pyselector.record.codegen import emit_pytest
from pyselector.utils.errors import (
    ActionNotAllowedError,
    ArgumentError,
    TargetWindowNotFoundError,
)


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch, tmp_path):
    monkeypatch.setenv("PYSELECTOR_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setattr(command_common, "setup_dpi_awareness", lambda: None)


class FakeLifecycleInspector:
    def __init__(self, windows=None):
        self.windows = windows if windows is not None else []
        self.actions = []

    def list_windows(self, only_visible=True):
        return list(self.windows)

    def find_window_by_handle(self, handle):
        for window in self.windows:
            if window.handle == handle:
                return window
        return ElementInfo(backend="uia", window_text="メモ帳", handle=handle, process_id=42, ref="w")

    def find_window_by_title(self, title, use_regex):
        return ElementInfo(backend="uia", window_text=title, handle=100, process_id=42, ref="w")

    def get_target_window(self, element):
        return TargetWindowInfo(
            backend="uia",
            title=element.window_text,
            handle=element.handle,
            process_id=element.process_id,
        )

    def perform_action(self, element, action, value=None):
        self.actions.append(action)
        return action


def _window(title="タイトルなし - メモ帳", handle=0x470D2A, pid=999):
    return ElementInfo(backend="uia", window_text=title, handle=handle, process_id=pid, ref="w")


def _launch_args(**overrides):
    values = dict(
        command="launch",
        exe="notepad.exe",
        app=None,
        args=None,
        wait_title_re="メモ帳$",
        timeout=5,
        attach_existing=False,
        backend="uia",
        note=None,
        allow_actions=True,
        env_allow_actions=True,
        dry_run=False,
        json=True,
        apps={},
        poll_interval=0.0,
    )
    values.update(overrides)
    return Namespace(**values)


def _close_args(**overrides):
    values = dict(
        command="close",
        window_handle=0x470D2A,
        window_title=None,
        title_re=False,
        force=False,
        backend="uia",
        note=None,
        allow_actions=True,
        env_allow_actions=True,
        dry_run=False,
        json=True,
    )
    values.update(overrides)
    return Namespace(**values)


def _run(monkeypatch, capsys, runner, inspector, args):
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    exit_code = runner(args)
    return exit_code, json.loads(capsys.readouterr().out)


def test_launch_waits_for_the_window_and_reports_its_handle(monkeypatch, capsys):
    inspector = FakeLifecycleInspector()
    started = []

    def fake_start(plan):
        started.append(plan)
        inspector.windows = [_window()]
        return 4242

    monkeypatch.setattr(lifecycle, "_start", fake_start)

    exit_code, payload = _run(monkeypatch, capsys, lifecycle.run_launch, inspector, _launch_args())

    assert exit_code == 0
    assert payload["pid"] == 4242
    assert payload["window"]["handle"] == 0x470D2A
    assert started[0]["exe"] == "notepad.exe"


def test_launch_is_gated_like_act(monkeypatch, capsys):
    """任意の実行ファイルを起動することは、ボタンを 1 つ押すことより軽くはない。"""
    inspector = FakeLifecycleInspector()
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(lifecycle, "_start", lambda plan: 1)

    with pytest.raises(ActionNotAllowedError):
        lifecycle.run_launch(_launch_args(allow_actions=False))

    with pytest.raises(ActionNotAllowedError):
        lifecycle.run_launch(_launch_args(env_allow_actions=False))


def test_a_dry_run_starts_nothing_and_needs_no_permission(monkeypatch, capsys):
    inspector = FakeLifecycleInspector()
    monkeypatch.setattr(lifecycle, "_start", lambda plan: pytest.fail("起動してはいけない"))

    exit_code, payload = _run(
        monkeypatch,
        capsys,
        lifecycle.run_launch,
        inspector,
        _launch_args(dry_run=True, allow_actions=False, env_allow_actions=False),
    )

    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["pid"] is None


def test_attach_existing_does_not_start_a_second_instance(monkeypatch, capsys):
    inspector = FakeLifecycleInspector(windows=[_window()])
    monkeypatch.setattr(lifecycle, "_start", lambda plan: pytest.fail("既に起動している"))

    exit_code, payload = _run(
        monkeypatch, capsys, lifecycle.run_launch, inspector, _launch_args(attach_existing=True)
    )

    assert exit_code == 0
    assert payload["attached"] is True
    assert payload["pid"] is None


def test_a_window_that_never_appears_is_an_error(monkeypatch, capsys):
    inspector = FakeLifecycleInspector()
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    monkeypatch.setattr(lifecycle, "_start", lambda plan: 7)

    with pytest.raises(TargetWindowNotFoundError):
        lifecycle.run_launch(_launch_args(timeout=1))


def test_the_title_pattern_wins_over_the_process_id(monkeypatch, capsys):
    """calc.exe のように、起動したプロセスとは別のプロセスがウィンドウを出すことがある。"""
    inspector = FakeLifecycleInspector(windows=[_window(pid=11111)])
    monkeypatch.setattr(lifecycle, "_start", lambda plan: 4242)

    exit_code, payload = _run(monkeypatch, capsys, lifecycle.run_launch, inspector, _launch_args())

    assert exit_code == 0
    assert payload["window"]["process_id"] == 11111


def test_an_unknown_app_name_is_rejected(monkeypatch):
    inspector = FakeLifecycleInspector()
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)

    with pytest.raises(ArgumentError):
        lifecycle.run_launch(_launch_args(exe=None, app="unknown", apps={"notepad": {"exe": "notepad.exe"}}))


def test_launch_needs_an_exe_or_an_app(monkeypatch):
    inspector = FakeLifecycleInspector()
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)

    with pytest.raises(ArgumentError):
        lifecycle.run_launch(_launch_args(exe=None, app=None))


def test_an_app_entry_supplies_the_defaults(monkeypatch, capsys):
    inspector = FakeLifecycleInspector()
    plans = []
    monkeypatch.setattr(lifecycle, "_start", lambda plan: plans.append(plan) or 5)
    inspector.windows = [_window()]

    apps = {"notepad": {"exe": "notepad.exe", "args": ["a.txt"], "window_title_re": "メモ帳$", "timeout": 12}}
    _run(
        monkeypatch,
        capsys,
        lifecycle.run_launch,
        inspector,
        _launch_args(exe=None, app="notepad", args=None, wait_title_re=None, timeout=None, apps=apps),
    )

    assert plans[0] == {
        "exe": "notepad.exe",
        "args": ["a.txt"],
        "window_title_re": "メモ帳$",
        "timeout": 12,
    }


def test_close_asks_the_window_to_close(monkeypatch, capsys):
    inspector = FakeLifecycleInspector(windows=[_window()])

    exit_code, payload = _run(monkeypatch, capsys, lifecycle.run_close, inspector, _close_args())

    assert exit_code == 0
    assert payload["performed"] is True
    assert inspector.actions == ["close"]


def test_close_is_gated(monkeypatch):
    inspector = FakeLifecycleInspector(windows=[_window()])
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)

    with pytest.raises(ActionNotAllowedError):
        lifecycle.run_close(_close_args(allow_actions=False))


def test_a_close_dry_run_touches_nothing(monkeypatch, capsys):
    inspector = FakeLifecycleInspector(windows=[_window()])

    exit_code, payload = _run(
        monkeypatch,
        capsys,
        lifecycle.run_close,
        inspector,
        _close_args(dry_run=True, allow_actions=False, env_allow_actions=False),
    )

    assert exit_code == 0
    assert payload["performed"] is False
    assert inspector.actions == []


def test_force_ends_the_process(monkeypatch, capsys):
    inspector = FakeLifecycleInspector(windows=[_window()])
    killed = []
    monkeypatch.setattr(lifecycle, "_terminate", lambda pid: killed.append(pid))

    exit_code, payload = _run(monkeypatch, capsys, lifecycle.run_close, inspector, _close_args(force=True))

    assert exit_code == 0
    assert killed == [999]
    assert payload["method"] == "terminate"
    assert inspector.actions == []


def test_a_recorded_launch_becomes_the_fixture(monkeypatch, capsys):
    inspector = FakeLifecycleInspector()
    monkeypatch.setattr(lifecycle, "_start", lambda plan: 4242)
    inspector.windows = [_window()]
    store.start("起動して閉じる")

    _run(monkeypatch, capsys, lifecycle.run_launch, inspector, _launch_args())
    _run(monkeypatch, capsys, lifecycle.run_close, inspector, _close_args())

    code = emit_pytest(store.load())
    assert 'Application(backend="uia").start(r"notepad.exe")' in code
    # close の対象はウィンドウ自身。同じタイトルの子を探すコードにしてはいけない。
    assert "window.close()" in code


def test_apps_config_is_validated(tmp_path, monkeypatch):
    config_path = tmp_path / "pyselector_config.json"
    config_path.write_text(
        json.dumps({"apps": {"notepad": {"exe": "notepad.exe", "window_title_re": "メモ帳$"}}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("PYSELECTOR_CONFIG", str(config_path))

    config = load_config()

    assert config.apps["notepad"]["exe"] == "notepad.exe"
    assert config.apps["notepad"]["timeout"] == 30


def test_an_app_entry_without_an_exe_is_rejected(tmp_path, monkeypatch):
    config_path = tmp_path / "pyselector_config.json"
    config_path.write_text(json.dumps({"apps": {"notepad": {"args": []}}}), encoding="utf-8")
    monkeypatch.setenv("PYSELECTOR_CONFIG", str(config_path))

    with pytest.raises(ArgumentError):
        load_config()


def test_an_unknown_app_key_is_rejected(tmp_path, monkeypatch):
    config_path = tmp_path / "pyselector_config.json"
    config_path.write_text(
        json.dumps({"apps": {"notepad": {"exe": "notepad.exe", "typo": 1}}}), encoding="utf-8"
    )
    monkeypatch.setenv("PYSELECTOR_CONFIG", str(config_path))

    with pytest.raises(ArgumentError):
        load_config()


def test_launch_prefers_a_window_that_was_not_there_before(monkeypatch, capsys):
    """同じアプリが既に開いていると、タイトルの正規表現だけでは古い方を掴む。"""
    old = _window(title="既存 - メモ帳", handle=0x111)
    inspector = FakeLifecycleInspector(windows=[old])

    def fake_start(plan):
        inspector.windows = [old, _window(title="タイトルなし - メモ帳", handle=0x222)]
        return 4242

    monkeypatch.setattr(lifecycle, "_start", fake_start)

    exit_code, payload = _run(monkeypatch, capsys, lifecycle.run_launch, inspector, _launch_args())

    assert exit_code == 0
    assert payload["window"]["handle"] == 0x222


def test_a_reused_window_is_still_accepted(monkeypatch, capsys):
    """新しいウィンドウを出さず既存を再利用するアプリもある。"""
    old = _window(title="既存 - メモ帳", handle=0x111)
    inspector = FakeLifecycleInspector(windows=[old])
    monkeypatch.setattr(lifecycle, "_start", lambda plan: 4242)

    exit_code, payload = _run(monkeypatch, capsys, lifecycle.run_launch, inspector, _launch_args())

    assert exit_code == 0
    assert payload["window"]["handle"] == 0x111


def test_a_forced_close_does_not_generate_a_plain_close(monkeypatch, capsys):
    """--force を close() にすると、意味が変わったまま静かに通ってしまう。"""
    inspector = FakeLifecycleInspector(windows=[_window()])
    monkeypatch.setattr(lifecycle, "_terminate", lambda pid: None)
    store.start("強制終了")

    _run(monkeypatch, capsys, lifecycle.run_close, inspector, _close_args(force=True))

    code = emit_pytest(store.load())
    assert ".kill()" in code
    assert "window.close()" not in code
