import json
from argparse import Namespace

import pytest

from pyselector import inspect_runner
from pyselector.commands import common as command_common
from pyselector.model.element_info import ElementInfo
from pyselector.model.rectangle import RectangleInfo


class FakeWindowsInspector:
    def __init__(self, backend="win32", windows=None, error=None):
        self.backend = backend
        self.windows = windows if windows is not None else _sample_windows(backend)
        self.error = error
        self.only_visible_calls = []

    def list_windows(self, only_visible=True):
        self.only_visible_calls.append(only_visible)
        if self.error is not None:
            raise self.error
        return self.windows


def _sample_windows(backend="win32"):
    return [
        ElementInfo(
            backend=backend,
            window_text="電卓",
            class_name="ApplicationFrameWindow",
            handle=100,
            process_id=11,
            rectangle=RectangleInfo(left=0, top=0, right=200, bottom=100),
            is_visible=True,
        ),
        ElementInfo(
            backend=backend,
            window_text="メモ帳",
            class_name="Notepad",
            handle=200,
            process_id=22,
            rectangle=RectangleInfo(left=10, top=10, right=110, bottom=60),
            is_visible=True,
        ),
        ElementInfo(backend=backend, window_text="", class_name="ThumbnailHelper", handle=300, process_id=33),
    ]


def _args(**overrides):
    base = dict(
        backend="win32",
        title=None,
        title_re=False,
        process=None,
        pid=None,
        include_untitled=False,
        only_visible=True,
        max_items=50,
        compact=False,
        json=True,
    )
    base.update(overrides)
    return Namespace(**base)


@pytest.fixture(autouse=True)
def process_names(monkeypatch):
    names = {11: "CalculatorApp.exe", 22: "notepad.exe", 33: "explorer.exe"}
    monkeypatch.setattr(command_common, "get_process_name", lambda pid: names.get(pid))


def _run(monkeypatch, capsys, inspector, args):
    monkeypatch.setattr(command_common, "_create_inspector", lambda backend: inspector)
    result = inspect_runner.run_windows(args)
    return result, capsys.readouterr().out


def test_windows_lists_titled_windows(monkeypatch, capsys):
    inspector = FakeWindowsInspector()

    result, output = _run(monkeypatch, capsys, inspector, _args())

    payload = json.loads(output)
    windows = payload["results"][0]["windows"]
    assert result == 0
    assert payload["status"] == "success"
    assert [window["title"] for window in windows] == ["電卓", "メモ帳"]
    assert windows[0]["handle"] == 100
    assert windows[0]["process_name"] == "CalculatorApp.exe"
    assert windows[0]["rectangle"]["width"] == 200


def test_windows_includes_untitled_when_requested(monkeypatch, capsys):
    inspector = FakeWindowsInspector()

    result, output = _run(monkeypatch, capsys, inspector, _args(include_untitled=True))

    windows = json.loads(output)["results"][0]["windows"]
    assert result == 0
    assert len(windows) == 3


def test_windows_filters_by_title_case_insensitively(monkeypatch, capsys):
    inspector = FakeWindowsInspector(
        windows=[ElementInfo(backend="win32", window_text="Calculator", handle=1, process_id=11)]
    )

    result, output = _run(monkeypatch, capsys, inspector, _args(title="calc"))

    assert result == 0
    assert [window["title"] for window in json.loads(output)["results"][0]["windows"]] == ["Calculator"]


def test_windows_filters_by_title_regex(monkeypatch, capsys):
    inspector = FakeWindowsInspector()

    result, output = _run(monkeypatch, capsys, inspector, _args(title="^メモ", title_re=True))

    assert result == 0
    assert [window["title"] for window in json.loads(output)["results"][0]["windows"]] == ["メモ帳"]


def test_windows_filters_by_process_name(monkeypatch, capsys):
    inspector = FakeWindowsInspector()

    result, output = _run(monkeypatch, capsys, inspector, _args(process="notepad"))

    assert result == 0
    assert [window["title"] for window in json.loads(output)["results"][0]["windows"]] == ["メモ帳"]


def test_windows_filters_by_pid(monkeypatch, capsys):
    inspector = FakeWindowsInspector()

    result, output = _run(monkeypatch, capsys, inspector, _args(pid=11))

    assert result == 0
    assert [window["title"] for window in json.loads(output)["results"][0]["windows"]] == ["電卓"]


def test_windows_truncates_to_max_items(monkeypatch, capsys):
    inspector = FakeWindowsInspector()

    result, output = _run(monkeypatch, capsys, inspector, _args(max_items=1))

    payload = json.loads(output)["results"][0]
    assert result == 0
    assert len(payload["windows"]) == 1
    assert payload["reached_limit"] is True


def test_windows_passes_only_visible_to_backend(monkeypatch, capsys):
    inspector = FakeWindowsInspector()

    _run(monkeypatch, capsys, inspector, _args(only_visible=False))

    assert inspector.only_visible_calls == [False]


def test_windows_returns_exit_code_1_with_success_status_when_nothing_matches(monkeypatch, capsys):
    inspector = FakeWindowsInspector()

    result, output = _run(monkeypatch, capsys, inspector, _args(title="存在しない"))

    payload = json.loads(output)
    assert result == 1
    assert payload["status"] == "success"
    assert payload["results"][0]["windows"] == []


def test_windows_reports_error_status_when_backend_fails(monkeypatch, capsys):
    inspector = FakeWindowsInspector(error=RuntimeError("boom"))

    result, output = _run(monkeypatch, capsys, inspector, _args())

    payload = json.loads(output)
    assert result == 1
    assert payload["status"] == "error"
    assert payload["results"][0]["status"] == "failed"
    assert payload["results"][0]["message"] == "boom"


def test_windows_compact_output_keeps_only_key_fields(monkeypatch, capsys):
    inspector = FakeWindowsInspector()

    _, output = _run(monkeypatch, capsys, inspector, _args(compact=True))

    window = json.loads(output)["results"][0]["windows"][0]
    assert set(window) == {"title", "class_name", "process_name", "handle"}


def test_windows_text_output_lists_handles(monkeypatch, capsys):
    inspector = FakeWindowsInspector()

    result, output = _run(monkeypatch, capsys, inspector, _args(json=False))

    assert result == 0
    assert "[Windows]" in output
    assert '0x64 "電卓"' in output
    assert 'process_name="CalculatorApp.exe"' in output
