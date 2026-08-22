import json
from argparse import Namespace

import pytest

from pyselector import inspect_runner
from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.rectangle import RectangleInfo
from pyselector.model.target_window import TargetWindowInfo


class FakeFindInspector:
    """walk_elements で要素を返し、ref ごとに別の階層を返すインスペクター。"""

    def __init__(self, backend="uia", elements=None, error=None):
        self.backend = backend
        self.elements = elements if elements is not None else _sample_elements(backend)
        self.error = error
        self.root_calls = []
        self.hierarchy_calls = []
        self.walk_calls = []

    def element_from_point(self, x, y):
        self.root_calls.append(("point", x, y))
        return ElementInfo(backend=self.backend, window_text="root", ref="root")

    def find_window_by_handle(self, handle):
        self.root_calls.append(("handle", handle))
        return ElementInfo(backend=self.backend, window_text="root", handle=handle, ref="root")

    def find_window_by_title(self, title, use_regex):
        self.root_calls.append(("title", title, use_regex))
        return ElementInfo(backend=self.backend, window_text=title, ref="root")

    def walk_elements(self, root, depth, max_items, only_visible, progress_callback=None):
        self.walk_calls.append((depth, max_items, only_visible))
        if self.error is not None:
            raise self.error
        elements = self.elements[:max_items]
        return elements, len(self.elements) > max_items

    def get_target_window(self, element):
        return TargetWindowInfo(backend=self.backend, title="親ウィンドウ", handle=999)

    def get_hierarchy(self, element):
        self.hierarchy_calls.append(element.ref)
        return [HierarchyNode(depth=0, window_text=element.ref)]

    def find_elements(self, scope, condition):
        return [], False

    def find_elements_chain(self, scope, steps, max_items):
        return [], False, None


def _element(backend="uia", ref="e", depth=1, top=0, left=0, **overrides):
    values = dict(
        backend=backend,
        depth=depth,
        rectangle=RectangleInfo(left=left, top=top, right=left + 20, bottom=top + 10),
        is_enabled=True,
        is_visible=True,
        ref=ref,
    )
    values.update(overrides)
    return ElementInfo(**values)


def _sample_elements(backend="uia"):
    return [
        _element(ref="a", depth=2, top=100, left=0, window_text="保存", control_type="Button", automation_id="saveBtn"),
        _element(ref="b", depth=1, top=50, left=0, window_text="ファイル名", control_type="Edit", class_name="Edit"),
        _element(ref="c", depth=2, top=100, left=50, window_text="保存しない", control_type="Button", is_enabled=False),
    ]


def _args(**overrides):
    base = dict(
        backend="uia",
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
        depth=8,
        max_items=200,
        limit=20,
        timeout=5,
        scope="window",
        with_selectors=False,
        selector_limit=3,
        only_visible=True,
        detail=False,
        compact=False,
        json=True,
        selector_evaluation_max_items=10,
        found_index_trial_count=3,
    )
    base.update(overrides)
    return Namespace(**base)


def _run(monkeypatch, capsys, inspector, args):
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)
    result = inspect_runner.run_find(args)
    return result, capsys.readouterr().out


def _matches(output):
    return json.loads(output)["results"][0]["matches"]


def test_find_returns_all_elements_without_conditions(monkeypatch, capsys):
    result, output = _run(monkeypatch, capsys, FakeFindInspector(), _args())

    payload = json.loads(output)["results"][0]
    assert result == 0
    assert payload["scanned"] == 3
    assert payload["total_matched"] == 3
    assert len(payload["matches"]) == 3


def test_find_reports_point_from_element_rectangle(monkeypatch, capsys):
    _, output = _run(monkeypatch, capsys, FakeFindInspector(), _args(auto_id="saveBtn"))

    match = _matches(output)[0]
    assert match["point"] == {"x": 10, "y": 105}
    assert match["depth"] == 2


def test_find_reports_null_point_when_rectangle_is_missing(monkeypatch, capsys):
    inspector = FakeFindInspector(elements=[_element(ref="a", rectangle=None, window_text="x")])

    _, output = _run(monkeypatch, capsys, inspector, _args())

    assert _matches(output)[0]["point"] is None


def test_find_matches_text_case_insensitively_as_substring(monkeypatch, capsys):
    inspector = FakeFindInspector(elements=[_element(ref="a", window_text="Save As")])

    _, output = _run(monkeypatch, capsys, inspector, _args(text="save"))

    assert len(_matches(output)) == 1


def test_find_matches_text_regex(monkeypatch, capsys):
    _, output = _run(monkeypatch, capsys, FakeFindInspector(), _args(text_re="^保存$"))

    assert [match["element"]["window_text"] for match in _matches(output)] == ["保存"]


def test_find_matches_control_type_case_insensitively(monkeypatch, capsys):
    _, output = _run(monkeypatch, capsys, FakeFindInspector(), _args(control_type="button"))

    assert len(_matches(output)) == 2


def test_find_matches_class_name_exactly(monkeypatch, capsys):
    _, output = _run(monkeypatch, capsys, FakeFindInspector(), _args(class_name="Edit"))

    assert [match["element"]["window_text"] for match in _matches(output)] == ["ファイル名"]


def test_find_combines_conditions_with_and(monkeypatch, capsys):
    _, output = _run(monkeypatch, capsys, FakeFindInspector(), _args(text="保存", control_type="Button"))

    assert [match["element"]["window_text"] for match in _matches(output)] == ["保存", "保存しない"]


def test_find_enabled_only_excludes_disabled_elements(monkeypatch, capsys):
    _, output = _run(monkeypatch, capsys, FakeFindInspector(), _args(control_type="Button", enabled_only=True))

    assert [match["element"]["window_text"] for match in _matches(output)] == ["保存"]


def test_find_sorts_matches_by_depth_then_position(monkeypatch, capsys):
    _, output = _run(monkeypatch, capsys, FakeFindInspector(), _args())

    assert [match["element"]["window_text"] for match in _matches(output)] == ["ファイル名", "保存", "保存しない"]


def test_find_truncates_matches_by_limit(monkeypatch, capsys):
    _, output = _run(monkeypatch, capsys, FakeFindInspector(), _args(limit=2))

    payload = json.loads(output)["results"][0]
    assert len(payload["matches"]) == 2
    assert payload["total_matched"] == 3
    assert payload["truncated"] is True


def test_find_reports_reached_limit_from_the_walk(monkeypatch, capsys):
    _, output = _run(monkeypatch, capsys, FakeFindInspector(), _args(max_items=2))

    payload = json.loads(output)["results"][0]
    assert payload["scanned"] == 2
    assert payload["reached_limit"] is True


def test_find_passes_walk_options_to_the_backend(monkeypatch, capsys):
    inspector = FakeFindInspector()

    _run(monkeypatch, capsys, inspector, _args(depth=3, max_items=25, only_visible=False))

    assert inspector.walk_calls == [(3, 25, False)]


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"window_handle": 42}, ("handle", 42)),
        ({"window_handle": None, "window_title": "電卓"}, ("title", "電卓", False)),
        ({"window_handle": None, "at": (10, 20)}, ("point", 10, 20)),
    ],
)
def test_find_resolves_the_search_root(monkeypatch, capsys, overrides, expected):
    inspector = FakeFindInspector()

    _run(monkeypatch, capsys, inspector, _args(**overrides))

    assert inspector.root_calls == [expected]


def test_find_without_selectors_does_not_build_inspections(monkeypatch, capsys):
    inspector = FakeFindInspector()

    _, output = _run(monkeypatch, capsys, inspector, _args())

    assert inspector.hierarchy_calls == []
    assert all("inspection" not in match for match in _matches(output))


def test_find_with_selectors_builds_inspections_up_to_selector_limit(monkeypatch, capsys):
    inspector = FakeFindInspector()

    _, output = _run(monkeypatch, capsys, inspector, _args(with_selectors=True, selector_limit=2))

    matches = _matches(output)
    assert [match["element"]["window_text"] for match in matches if "inspection" in match] == ["ファイル名", "保存"]
    assert len(matches) == 3


def test_find_with_selectors_resolves_each_match_separately(monkeypatch, capsys):
    """UIA のように handle を持たない要素でも、一致要素ごとの階層が取得できること。"""
    inspector = FakeFindInspector()

    _, output = _run(monkeypatch, capsys, inspector, _args(with_selectors=True))

    assert inspector.hierarchy_calls == ["b", "a", "c"]
    hierarchies = [match["inspection"]["hierarchy"][0]["window_text"] for match in _matches(output)]
    assert hierarchies == ["b", "a", "c"]


def test_find_with_selectors_uses_the_element_center_for_evaluation(monkeypatch, capsys):
    inspector = FakeFindInspector(elements=[_element(ref="a", top=100, left=0, window_text="保存")])
    captured = {}

    def fake_evaluate(candidates, inspector_arg, scope, timeout, max_items, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(inspect_runner, "evaluate_candidates", fake_evaluate)

    _run(monkeypatch, capsys, inspector, _args(with_selectors=True))

    assert captured["cursor_position"].x == 10
    assert captured["cursor_position"].y == 105


def test_find_returns_exit_code_1_with_success_status_when_nothing_matches(monkeypatch, capsys):
    result, output = _run(monkeypatch, capsys, FakeFindInspector(), _args(text="存在しない"))

    payload = json.loads(output)
    assert result == 1
    assert payload["status"] == "success"
    assert payload["results"][0]["matches"] == []
    assert payload["results"][0]["total_matched"] == 0


def test_find_reports_error_status_when_backend_fails(monkeypatch, capsys):
    inspector = FakeFindInspector(error=RuntimeError("boom"))

    result, output = _run(monkeypatch, capsys, inspector, _args())

    payload = json.loads(output)
    assert result == 1
    assert payload["status"] == "error"
    assert payload["results"][0]["status"] == "failed"
    assert payload["results"][0]["message"] == "boom"


def test_find_compact_output_keeps_only_key_fields(monkeypatch, capsys):
    _, output = _run(monkeypatch, capsys, FakeFindInspector(), _args(compact=True))

    element = _matches(output)[0]["element"]
    assert set(element) == {"window_text", "control_type", "automation_id", "class_name"}


def test_find_text_output_shows_point_and_counts(monkeypatch, capsys):
    result, output = _run(monkeypatch, capsys, FakeFindInspector(), _args(json=False, control_type="Button"))

    assert result == 0
    assert "[Find]" in output
    assert "scanned: 3, matched: 2" in output
    assert "point=10,105" in output
