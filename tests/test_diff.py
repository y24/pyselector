import json

import pytest

from pyselector.diff import diff_nodes, diff_tree_payloads, load_tree_payload
from pyselector.utils.errors import ArgumentError


def _node(depth=1, control_type="Button", class_name="Button", automation_id="", window_text="", **extra):
    node = {
        "depth": depth,
        "window_text": window_text,
        "control_type": control_type,
        "automation_id": automation_id,
        "class_name": class_name,
        "friendly_class_name": class_name,
        "control_id": None,
        "handle": None,
        "rectangle": None,
    }
    node.update(extra)
    return node


def _payload(nodes, backend="uia", status="success", include_nodes=True):
    result = {"backend": backend, "status": status, "message": None, "root": None, "reached_limit": False}
    if include_nodes:
        result["nodes"] = nodes
    return {"schema_version": 1, "command": "tree", "status": "success", "results": [result]}


def test_identical_trees_have_no_differences():
    nodes = [_node(automation_id="a"), _node(automation_id="b")]

    diff = diff_nodes("uia", nodes, list(nodes))

    assert diff.has_differences is False
    assert diff.unchanged == 2


def test_added_nodes_are_detected():
    before = [_node(automation_id="a")]
    after = [_node(automation_id="a"), _node(automation_id="b", window_text="新規")]

    diff = diff_nodes("uia", before, after)

    assert [node["automation_id"] for node in diff.added] == ["b"]
    assert diff.removed == []
    assert diff.unchanged == 1


def test_removed_nodes_are_detected():
    before = [_node(automation_id="a"), _node(automation_id="b")]
    after = [_node(automation_id="a")]

    diff = diff_nodes("uia", before, after)

    assert [node["automation_id"] for node in diff.removed] == ["b"]
    assert diff.added == []


def test_changed_text_is_reported_with_before_and_after():
    before = [_node(automation_id="result", window_text="表示は 0 です")]
    after = [_node(automation_id="result", window_text="表示は 5 です")]

    diff = diff_nodes("uia", before, after)

    assert diff.added == []
    assert diff.removed == []
    assert len(diff.changed) == 1
    assert diff.changed[0].changes == {
        "window_text": {"before": "表示は 0 です", "after": "表示は 5 です"}
    }


def test_rectangle_changes_are_reported():
    before = [_node(automation_id="a", rectangle={"left": 0, "top": 0, "right": 10, "bottom": 10})]
    after = [_node(automation_id="a", rectangle={"left": 5, "top": 0, "right": 15, "bottom": 10})]

    diff = diff_nodes("uia", before, after)

    assert "rectangle" in diff.changed[0].changes


def test_identical_siblings_are_paired_by_occurrence_order():
    before = [_node(window_text="1"), _node(window_text="2"), _node(window_text="3")]
    after = [_node(window_text="1"), _node(window_text="9"), _node(window_text="3")]

    diff = diff_nodes("uia", before, after)

    assert diff.added == []
    assert diff.removed == []
    assert len(diff.changed) == 1
    assert diff.changed[0].changes["window_text"] == {"before": "2", "after": "9"}


def test_nodes_at_a_different_depth_are_not_paired():
    diff = diff_nodes("uia", [_node(depth=1, automation_id="a")], [_node(depth=2, automation_id="a")])

    assert len(diff.added) == 1
    assert len(diff.removed) == 1
    assert diff.changed == []


def test_diff_tree_payloads_pairs_results_by_backend():
    before = _payload([_node(automation_id="a")])
    after = _payload([_node(automation_id="a"), _node(automation_id="b")])

    diffs = diff_tree_payloads(before, after)

    assert [diff.backend for diff in diffs] == ["uia"]
    assert len(diffs[0].added) == 1


def test_missing_backend_on_one_side_is_reported_as_failed():
    before = _payload([_node()], backend="uia")
    after = _payload([_node()], backend="win32")

    diffs = {diff.backend: diff for diff in diff_tree_payloads(before, after)}

    assert diffs["uia"].status == "failed"
    assert "after 側に uia の結果がありません" in diffs["uia"].message
    assert diffs["win32"].status == "failed"


def test_summary_output_cannot_be_compared():
    before = _payload([], include_nodes=False)
    after = _payload([_node()])

    diff = diff_tree_payloads(before, after)[0]

    assert diff.status == "failed"
    assert "--summary" in diff.message


def test_failed_tree_result_is_reported_as_failed():
    before = _payload([_node()], status="failed")
    after = _payload([_node()])

    diff = diff_tree_payloads(before, after)[0]

    assert diff.status == "failed"
    assert "before 側の取得が失敗" in diff.message


def test_load_tree_payload_reads_a_tree_output(tmp_path):
    path = tmp_path / "before.json"
    path.write_text(json.dumps(_payload([_node()]), ensure_ascii=False), encoding="utf-8")

    payload = load_tree_payload(path)

    assert payload["command"] == "tree"


def test_load_tree_payload_rejects_other_commands(tmp_path):
    path = tmp_path / "find.json"
    path.write_text('{"command": "find", "results": []}', encoding="utf-8")

    with pytest.raises(ArgumentError) as error:
        load_tree_payload(path)

    assert "tree --json の出力ではありません" in str(error.value)


def test_load_tree_payload_rejects_broken_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(ArgumentError) as error:
        load_tree_payload(path)

    assert "JSON として解析できません" in str(error.value)


def test_load_tree_payload_reports_a_missing_file(tmp_path):
    with pytest.raises(ArgumentError) as error:
        load_tree_payload(tmp_path / "nope.json")

    assert "ファイルを読み込めません" in str(error.value)
