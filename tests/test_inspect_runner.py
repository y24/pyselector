from argparse import Namespace

from pyselector import inspect_runner
from pyselector.model.element_info import ElementInfo
from pyselector.model.inspection_result import CursorPosition
from pyselector.model.target_window import TargetWindowInfo


class FailingInspector:
    def element_from_point(self, x, y):
        raise RuntimeError("boom")


class ControlTypeOnlyInspector:
    def __init__(self):
        self.conditions = []

    def element_from_point(self, x, y):
        return ElementInfo(backend="uia", control_type="CheckBox")

    def get_target_window(self, element):
        return TargetWindowInfo(backend="uia", handle=100)

    def get_hierarchy(self, element):
        return []

    def find_elements(self, scope, condition):
        self.conditions.append(condition)
        return [], False


class ClassNameOnlyInspector:
    def __init__(self):
        self.conditions = []

    def element_from_point(self, x, y):
        return ElementInfo(backend="win32", class_name="Button")

    def get_target_window(self, element):
        return TargetWindowInfo(backend="win32", handle=100)

    def get_hierarchy(self, element):
        return []

    def find_elements(self, scope, condition):
        self.conditions.append(condition)
        return [], False


def test_inspect_logs_timeout_before_countdown(monkeypatch, capsys):
    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: None)
    monkeypatch.setattr(inspect_runner, "get_cursor_position", lambda: CursorPosition(10, 20))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: FailingInspector())

    result = inspect_runner.run_inspect(
        Namespace(delay=5, timeout=12, backend="uia", detail=False, scope="window", only_visible=False, max_items=None)
    )

    lines = capsys.readouterr().out.splitlines()
    assert result == 1
    assert lines[:3] == [
        "[INFO] pyselector started",
        "[INFO] selector validation timeout: 12 sec",
        "[INFO] countdown: 5 sec",
    ]
    assert "[INFO] selector hit count limit: 10" not in lines
    assert "[INFO] uia: カーソル下の要素を取得中です..." not in lines


def test_inspect_does_not_evaluate_control_type_only_candidate(monkeypatch, capsys):
    inspector = ControlTypeOnlyInspector()
    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: None)
    monkeypatch.setattr(inspect_runner, "get_cursor_position", lambda: CursorPosition(10, 20))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    result = inspect_runner.run_inspect(
        Namespace(delay=0, timeout=12, backend="uia", detail=False, scope="window", only_visible=False, max_items=None)
    )

    capsys.readouterr()
    assert result == 0
    assert inspector.conditions == []


def test_inspect_does_not_evaluate_class_name_only_candidate(monkeypatch, capsys):
    inspector = ClassNameOnlyInspector()
    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: None)
    monkeypatch.setattr(inspect_runner, "get_cursor_position", lambda: CursorPosition(10, 20))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    result = inspect_runner.run_inspect(
        Namespace(delay=0, timeout=12, backend="win32", detail=False, scope="window", only_visible=False, max_items=None)
    )

    capsys.readouterr()
    assert result == 0
    assert inspector.conditions == []
