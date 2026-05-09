from argparse import Namespace

from pyselector import inspect_runner
from pyselector.model.inspection_result import CursorPosition


class FailingInspector:
    def element_from_point(self, x, y):
        raise RuntimeError("boom")


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
    assert "[INFO] UI要素の情報を取得中です..." in lines
    assert "[INFO] selector hit count limit: 10" in lines
    assert "[INFO] uia: カーソル下の要素を取得中です..." in lines
