import json
from argparse import Namespace
from pathlib import Path

import pytest

from pyselector import cli, inspect_runner
from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.inspection_result import BackendInspection, CursorPosition, InspectionResult, TreeResult
from pyselector.model.selector_candidate import SelectorCandidate, SelectorEvaluation
from pyselector.model.target_window import TargetWindowInfo
from pyselector.output.json_output import (
    SCHEMA_VERSION,
    format_error_json,
    format_inspection_result_json,
    format_tree_results_json,
)


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def default_config(monkeypatch):
    monkeypatch.delenv("PYSELECTOR_CONFIG", raising=False)
    monkeypatch.chdir(FIXTURES)


def _inspection_result(status="success"):
    candidate = SelectorCandidate(
        backend="win32",
        selector_text='dlg.child_window(class_name="Button")',
        selector_kind="win32_class_name",
        condition={"class_name": "Button"},
    )
    inspection = BackendInspection(
        backend="win32",
        element=ElementInfo(backend="win32", window_text="OK"),
        target_window=TargetWindowInfo(backend="win32", title="電卓", handle=100),
        hierarchy=[HierarchyNode(depth=0, window_text="電卓")],
        evaluations=[SelectorEvaluation(candidate=candidate, hits=1)],
        code_snippet="print('ok')",
        status=status,
    )
    return InspectionResult(cursor_position=CursorPosition(x=10, y=20), win32=inspection)


def test_inspect_json_carries_the_envelope():
    payload = json.loads(format_inspection_result_json(_inspection_result()))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["command"] == "inspect"
    assert payload["status"] == "success"


def test_inspect_json_keeps_the_existing_keys():
    payload = json.loads(format_inspection_result_json(_inspection_result()))

    assert payload["cursor_position"] == {"x": 10, "y": 20}
    assert payload["target_window"]["title"] == "電卓"
    backend = payload["backends"][0]
    assert set(backend) == {
        "backend",
        "status",
        "message",
        "target_window",
        "element",
        "hierarchy",
        "selector_candidates",
        "code_snippet",
    }
    assert set(backend["element"]) == {
        "backend",
        "window_text",
        "control_type",
        "automation_id",
        "class_name",
        "friendly_class_name",
        "control_id",
        "children_count",
        "depth",
        "rectangle",
        "is_visible",
        "is_enabled",
        "handle",
        "process_id",
        "process_name",
    }
    assert set(backend["selector_candidates"][0]) == {
        "selector_text",
        "selector_kind",
        "hits",
        "status",
        "warnings",
        "reached_limit",
        "parent_hits",
        "error_message",
        "candidate",
    }


def test_inspect_json_reports_error_status_when_every_backend_failed():
    payload = json.loads(format_inspection_result_json(_inspection_result(status="failed")))

    assert payload["status"] == "error"


def test_tree_json_keeps_the_existing_keys():
    result = TreeResult(
        backend="uia",
        root=ElementInfo(backend="uia", window_text="電卓"),
        nodes=[HierarchyNode(depth=0, window_text="電卓", class_name="Window")],
        reached_limit=False,
    )

    payload = json.loads(format_tree_results_json([result]))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["command"] == "tree"
    assert payload["status"] == "success"
    tree = payload["results"][0]
    assert set(tree) == {"backend", "status", "message", "root", "reached_limit", "nodes"}
    assert set(tree["nodes"][0]) == {
        "depth",
        "window_text",
        "control_type",
        "automation_id",
        "class_name",
        "friendly_class_name",
        "control_id",
        "handle",
        "rectangle",
    }


def test_tree_summary_replaces_nodes_with_counts():
    result = TreeResult(
        backend="uia",
        root=ElementInfo(backend="uia", window_text="電卓"),
        nodes=[
            HierarchyNode(depth=0, control_type="Window", class_name="Frame"),
            HierarchyNode(depth=1, control_type="Button", class_name="Button"),
            HierarchyNode(depth=2, control_type="Button", class_name="Button"),
        ],
        reached_limit=False,
    )

    tree = json.loads(format_tree_results_json([result], summary=True))["results"][0]

    assert "nodes" not in tree
    assert tree["summary"]["total"] == 3
    assert tree["summary"]["max_depth"] == 2
    assert tree["summary"]["by_control_type"] == {"Button": 2, "Window": 1}


def test_error_json_shape():
    payload = json.loads(format_error_json("find", "element_not_found", 1, "見つかりません"))

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["command"] == "find"
    assert payload["status"] == "error"
    assert payload["error"] == {"code": "element_not_found", "exit_code": 1, "message": "見つかりません"}


def test_cli_reports_pyselector_errors_as_json(monkeypatch, capsys):
    from pyselector.utils.errors import ElementNotFoundError

    def fake_run_find(args):
        raise ElementNotFoundError("一致するウィンドウ数が 3 件です")

    monkeypatch.setattr(cli, "run_find", fake_run_find)

    result = cli.main(["find", "--json", "--window-title", "電卓"])

    payload = json.loads(capsys.readouterr().out)
    assert result == 1
    assert payload["command"] == "find"
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "element_not_found"
    assert payload["error"]["exit_code"] == 1
    assert payload["error"]["message"] == "一致するウィンドウ数が 3 件です"


def test_cli_reports_argument_errors_as_json(capsys):
    result = cli.main(["find", "--json", "--window-handle", "0x10", "--limit", "0"])

    payload = json.loads(capsys.readouterr().out)
    assert result == 10
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "argument_error"
    assert payload["error"]["exit_code"] == 10


def test_cli_does_not_emit_json_without_the_flag(monkeypatch, capsys):
    from pyselector.utils.errors import ElementNotFoundError

    monkeypatch.setattr(cli, "run_find", lambda args: (_ for _ in ()).throw(ElementNotFoundError("boom")))

    result = cli.main(["find", "--window-title", "電卓"])

    captured = capsys.readouterr()
    assert result == 1
    assert "{" not in captured.out
    assert "[ERROR] boom" in captured.err


def test_cli_reports_unexpected_errors_as_json(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_windows", lambda args: (_ for _ in ()).throw(RuntimeError("boom")))

    result = cli.main(["windows", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert result == 100
    assert payload["error"]["code"] == "unexpected_error"
    assert payload["error"]["message"] == "boom"


def test_version_json_reports_the_schema_version(capsys):
    result = cli.main(["version", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["command"] == "version"
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["version"]


def test_version_text_output_is_unchanged(capsys):
    from pyselector import __version__

    result = cli.main(["version"])

    assert result == 0
    assert capsys.readouterr().out.splitlines()[-1] == f"pyselector {__version__}"


def test_inspect_json_still_saves_a_log_file(monkeypatch, capsys):
    saved = []
    monkeypatch.setattr(inspect_runner, "save_inspection_log", lambda result, content, **kwargs: saved.append(kwargs))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: _FailingInspector())

    inspect_runner.run_inspect(
        Namespace(
            delay=0,
            timeout=12,
            backend="uia",
            detail=False,
            scope="window",
            only_visible=False,
            max_items=None,
            json=True,
        ),
        point_selector=lambda: (10, 20),
    )

    payload = json.loads(capsys.readouterr().out)
    assert saved[0]["suffix"] == ".json"
    assert payload["status"] == "error"


class _FailingInspector:
    def element_from_point(self, x, y):
        raise RuntimeError("boom")
