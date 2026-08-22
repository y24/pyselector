import json
from argparse import Namespace

import pytest

from pyselector import inspect_runner
from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.rectangle import RectangleInfo
from pyselector.model.target_window import TargetWindowInfo
from pyselector.utils.errors import ActionFailedError, ActionNotAllowedError, AmbiguousTargetError, ElementNotFoundError


class FakeActInspector:
    def __init__(self, elements=None, action_error=None):
        self.backend = "uia"
        self.elements = elements if elements is not None else _sample_elements()
        self.action_error = action_error
        self.actions = []
        self.root_calls = []
        self.display = "0"

    def element_from_point(self, x, y):
        self.root_calls.append(("point", x, y))
        return ElementInfo(
            backend="uia",
            window_text="座標の要素",
            ref="point",
            rectangle=RectangleInfo(left=x - 5, top=y - 5, right=x + 5, bottom=y + 5),
        )

    def find_window_by_handle(self, handle):
        self.root_calls.append(("handle", handle))
        return ElementInfo(backend="uia", window_text="電卓", handle=handle, ref="root")

    def find_window_by_title(self, title, use_regex):
        self.root_calls.append(("title", title, use_regex))
        return ElementInfo(backend="uia", window_text=title, ref="root")

    def walk_elements(self, root, depth, max_items, only_visible, progress_callback=None):
        return list(self.elements), False

    def walk_tree(self, root, depth, max_items, only_visible, progress_callback=None):
        return [
            HierarchyNode(depth=4, window_text=f"表示は {self.display} です", automation_id="CalculatorResults"),
            HierarchyNode(depth=5, window_text="5", automation_id="num5Button", control_type="Button"),
        ], False

    def get_target_window(self, element):
        return TargetWindowInfo(backend="uia", title="電卓", handle=100)

    def perform_action(self, element, action, value=None):
        if self.action_error is not None:
            raise self.action_error
        self.actions.append((element.ref, action, value))
        self.display = value if action == "send_keys" else "5"
        return "click_input"

    def refresh_element(self, element):
        return ElementInfo(backend="uia", window_text="押された後", ref=element.ref)


def _element(ref, window_text, **overrides):
    values = dict(
        backend="uia",
        window_text=window_text,
        control_type="Button",
        class_name="Button",
        depth=5,
        rectangle=RectangleInfo(left=0, top=0, right=20, bottom=10),
        is_enabled=True,
        ref=ref,
    )
    values.update(overrides)
    return ElementInfo(**values)


def _sample_elements():
    return [
        _element("a", "5", automation_id="num5Button"),
        _element("b", "6", automation_id="num6Button"),
    ]


def _args(**overrides):
    base = dict(
        backend="uia",
        action="click",
        value=None,
        window_handle=100,
        window_title=None,
        title_re=False,
        at=None,
        text=None,
        text_re=None,
        auto_id=None,
        control_type=None,
        class_name=None,
        enabled_only=False,
        index=None,
        depth=8,
        max_items=200,
        only_visible=True,
        allow_actions=True,
        config_allow_actions=True,
        dry_run=False,
        diff=False,
        json=True,
    )
    base.update(overrides)
    return Namespace(**base)


def _run(monkeypatch, capsys, inspector, args):
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)
    result = inspect_runner.run_act(args)
    return result, capsys.readouterr().out


def test_act_clicks_the_single_matching_element(monkeypatch, capsys):
    inspector = FakeActInspector()

    result, output = _run(monkeypatch, capsys, inspector, _args(auto_id="num5Button"))

    payload = json.loads(output)
    assert result == 0
    assert inspector.actions == [("a", "click", None)]
    assert payload["command"] == "act"
    assert payload["status"] == "success"
    assert payload["performed"] is True
    assert payload["method"] == "click_input"
    assert payload["point"] == {"x": 10, "y": 5}
    assert payload["target"]["automation_id"] == "num5Button"
    assert payload["element_after"]["window_text"] == "押された後"


def test_act_requires_the_config_flag(monkeypatch, capsys):
    inspector = FakeActInspector()
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    with pytest.raises(ActionNotAllowedError) as error:
        inspect_runner.run_act(_args(auto_id="num5Button", config_allow_actions=False))

    capsys.readouterr()
    assert "allow_actions" in str(error.value)
    assert inspector.actions == []


def test_act_requires_the_allow_actions_flag(monkeypatch, capsys):
    inspector = FakeActInspector()
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    with pytest.raises(ActionNotAllowedError) as error:
        inspect_runner.run_act(_args(auto_id="num5Button", allow_actions=False))

    capsys.readouterr()
    assert "--allow-actions" in str(error.value)
    assert inspector.actions == []


def test_dry_run_resolves_the_target_without_acting(monkeypatch, capsys):
    inspector = FakeActInspector()

    result, output = _run(
        monkeypatch,
        capsys,
        inspector,
        _args(auto_id="num5Button", dry_run=True, allow_actions=False, config_allow_actions=False),
    )

    payload = json.loads(output)
    assert result == 0
    assert inspector.actions == []
    assert payload["dry_run"] is True
    assert payload["performed"] is False
    assert payload["target"]["automation_id"] == "num5Button"


def test_act_refuses_an_ambiguous_target(monkeypatch, capsys):
    inspector = FakeActInspector()
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    with pytest.raises(AmbiguousTargetError) as error:
        inspect_runner.run_act(_args(control_type="Button"))

    capsys.readouterr()
    message = str(error.value)
    assert "2 件あります" in message
    assert "[0] '5'" in message
    assert inspector.actions == []


def test_index_selects_among_several_matches(monkeypatch, capsys):
    inspector = FakeActInspector()

    result, _ = _run(monkeypatch, capsys, inspector, _args(control_type="Button", index=1))

    assert result == 0
    assert inspector.actions == [("b", "click", None)]


def test_index_out_of_range_is_rejected(monkeypatch, capsys):
    inspector = FakeActInspector()
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    with pytest.raises(ElementNotFoundError) as error:
        inspect_runner.run_act(_args(control_type="Button", index=9))

    capsys.readouterr()
    assert "index=9 は範囲外です" in str(error.value)


def test_no_match_is_rejected(monkeypatch, capsys):
    inspector = FakeActInspector()
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    with pytest.raises(ElementNotFoundError):
        inspect_runner.run_act(_args(auto_id="存在しない"))

    capsys.readouterr()
    assert inspector.actions == []


def test_at_targets_the_element_directly(monkeypatch, capsys):
    inspector = FakeActInspector()

    result, output = _run(monkeypatch, capsys, inspector, _args(window_handle=None, at=(50, 60)))

    payload = json.loads(output)
    assert result == 0
    assert inspector.root_calls == [("point", 50, 60)]
    assert payload["target"]["window_text"] == "座標の要素"
    assert inspector.actions == [("point", "click", None)]


def test_send_keys_passes_the_value(monkeypatch, capsys):
    inspector = FakeActInspector()

    result, output = _run(monkeypatch, capsys, inspector, _args(auto_id="num5Button", action="send_keys", value="7"))

    payload = json.loads(output)
    assert result == 0
    assert inspector.actions == [("a", "send_keys", "7")]
    assert payload["value"] == "7"


def test_action_failure_propagates(monkeypatch, capsys):
    inspector = FakeActInspector(action_error=ActionFailedError("boom"))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    with pytest.raises(ActionFailedError):
        inspect_runner.run_act(_args(auto_id="num5Button"))

    capsys.readouterr()


def test_diff_reports_what_changed_around_the_action(monkeypatch, capsys):
    inspector = FakeActInspector()

    result, output = _run(monkeypatch, capsys, inspector, _args(auto_id="num5Button", diff=True))

    payload = json.loads(output)
    assert result == 0
    diff = payload["diff"]
    assert diff["has_differences"] is True
    assert diff["summary"] == {"added": 0, "removed": 0, "changed": 1, "unchanged": 1}
    assert diff["changed"][0]["changes"]["window_text"] == {
        "before": "表示は 0 です",
        "after": "表示は 5 です",
    }


def test_diff_is_skipped_for_a_dry_run(monkeypatch, capsys):
    inspector = FakeActInspector()

    _, output = _run(monkeypatch, capsys, inspector, _args(auto_id="num5Button", diff=True, dry_run=True))

    assert "diff" not in json.loads(output)


def test_text_output_shows_the_target_and_result(monkeypatch, capsys):
    inspector = FakeActInspector()

    result, output = _run(monkeypatch, capsys, inspector, _args(auto_id="num5Button", json=False))

    assert result == 0
    assert "[Act]" in output
    assert "action: click" in output
    assert "performed: True" in output
    assert 'target: "5"' in output
