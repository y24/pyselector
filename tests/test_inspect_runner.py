import json
from argparse import Namespace
from pathlib import Path

import pytest

from pyselector import inspect_runner
from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.inspection_result import CursorPosition
from pyselector.model.selector_candidate import SelectorCandidate, SelectorEvaluation
from pyselector.model.target_window import TargetWindowInfo


@pytest.fixture(autouse=True)
def disable_inspect_log_file(monkeypatch):
    monkeypatch.setattr(inspect_runner, "save_inspection_log", lambda *args, **kwargs: None)


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


class SuccessfulInspector:
    def __init__(self, backend):
        self.backend = backend

    def element_from_point(self, x, y):
        return ElementInfo(backend=self.backend)

    def get_target_window(self, element):
        return TargetWindowInfo(backend=self.backend, handle=100)

    def get_hierarchy(self, element):
        return []


class TreeInspector:
    def __init__(self, backend):
        self.backend = backend

    def find_window_by_title(self, title, title_re):
        return ElementInfo(backend=self.backend, window_text=title)

    def walk_tree(self, root, depth, max_items, only_visible, progress_callback=None):
        if progress_callback is not None:
            progress_callback(1, max_items)
        return [HierarchyNode(depth=0, window_text=root.window_text, class_name="Window")], False


def test_inspect_cancel_returns_without_creating_inspector(monkeypatch, capsys):
    created = []
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: created.append(backend))

    result = inspect_runner.run_inspect(
        Namespace(delay=0, timeout=12, backend="uia", detail=False, scope="window", only_visible=False, max_items=None),
        point_selector=lambda: None,
    )

    lines = capsys.readouterr().out.splitlines()
    assert result == 1
    assert created == []
    assert "[INFO] 選択をキャンセルしました。" in lines


def test_inspect_uses_overlay_when_delay_is_not_specified(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(inspect_runner, "select_point_with_overlay", lambda: calls.append("overlay") or (10, 20))
    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: calls.append("countdown"))
    monkeypatch.setattr(inspect_runner, "get_cursor_position", lambda: calls.append("cursor") or CursorPosition(30, 40))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: FailingInspector())

    result = inspect_runner.run_inspect(
        Namespace(delay=None, timeout=12, backend="uia", detail=False, scope="window", only_visible=False, max_items=None)
    )

    capsys.readouterr()
    assert result == 1
    assert calls == ["overlay"]


def test_inspect_uses_countdown_when_delay_is_specified(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(inspect_runner, "select_point_with_overlay", lambda: calls.append("overlay") or (10, 20))
    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: calls.append(("countdown", delay)))
    monkeypatch.setattr(inspect_runner, "get_cursor_position", lambda: calls.append("cursor") or CursorPosition(30, 40))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: FailingInspector())

    result = inspect_runner.run_inspect(
        Namespace(delay=5, timeout=12, backend="uia", detail=False, scope="window", only_visible=False, max_items=None)
    )

    output = capsys.readouterr().out
    assert result == 1
    assert calls == [("countdown", 5), "cursor"]
    assert "[INFO] 座標を決定しました。 X=30, Y=40" in output


def test_inspect_does_not_log_timeout_before_countdown(monkeypatch, capsys):
    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: None)
    monkeypatch.setattr(inspect_runner, "get_cursor_position", lambda: CursorPosition(10, 20))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: FailingInspector())

    result = inspect_runner.run_inspect(
        Namespace(delay=5, timeout=12, backend="uia", detail=False, scope="window", only_visible=False, max_items=None),
        point_selector=lambda: (10, 20),
    )

    lines = capsys.readouterr().out.splitlines()
    assert result == 1
    assert lines[:1] == ["[INFO] pyselector started"]
    assert "[INFO] selector validation total timeout: 12 sec" not in lines
    assert "[INFO] selector hit count limit: 10" not in lines
    assert "[INFO] uia: カーソル下の要素を取得中です..." in lines


def test_inspect_logs_loaded_config_after_start(monkeypatch, capsys):
    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: None)
    monkeypatch.setattr(inspect_runner, "get_cursor_position", lambda: CursorPosition(10, 20))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: FailingInspector())

    result = inspect_runner.run_inspect(
        Namespace(
            delay=5,
            timeout=12,
            backend="uia",
            detail=False,
            scope="window",
            only_visible=False,
            max_items=None,
            config_path=Path("pyselector_config.json"),
        ),
        point_selector=lambda: (10, 20),
    )

    lines = capsys.readouterr().out.splitlines()
    assert result == 1
    assert lines[:2] == [
        "[INFO] pyselector started",
        "[INFO] pyselector_config.json loaded",
    ]
    assert "[INFO] selector validation total timeout: 12 sec" not in lines


def test_inspect_does_not_evaluate_control_type_only_candidate(monkeypatch, capsys):
    inspector = ControlTypeOnlyInspector()
    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: None)
    monkeypatch.setattr(inspect_runner, "get_cursor_position", lambda: CursorPosition(10, 20))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    result = inspect_runner.run_inspect(
        Namespace(delay=0, timeout=12, backend="uia", detail=False, scope="window", only_visible=False, max_items=None),
        point_selector=lambda: (10, 20),
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
        Namespace(delay=0, timeout=12, backend="win32", detail=False, scope="window", only_visible=False, max_items=None),
        point_selector=lambda: (10, 20),
    )

    capsys.readouterr()
    assert result == 0
    assert inspector.conditions == []


def test_inspect_logs_hit_candidate_count_after_evaluation(monkeypatch, capsys):
    candidate = SelectorCandidate(
        backend="win32",
        selector_text='dlg.child_window(class_name="Button")',
        selector_kind="win32_class_name",
        condition={"class_name": "Button"},
    )
    evaluations = [
        SelectorEvaluation(candidate=candidate, hits=1),
        SelectorEvaluation(candidate=candidate, hits=0),
        SelectorEvaluation(candidate=candidate, hits=None, status="timeout"),
    ]

    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: None)
    monkeypatch.setattr(inspect_runner, "get_cursor_position", lambda: CursorPosition(10, 20))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: SuccessfulInspector(backend))
    monkeypatch.setattr(inspect_runner, "generate_candidates", lambda element, hierarchy: [candidate, candidate, candidate])
    monkeypatch.setattr(inspect_runner, "evaluate_candidates", lambda *args, **kwargs: evaluations)
    monkeypatch.setattr(inspect_runner, "append_found_index_candidates", lambda candidates, evaluations, element: candidates)
    monkeypatch.setattr(inspect_runner, "sort_candidates", lambda candidates: candidates)
    monkeypatch.setattr(inspect_runner, "deduplicate_candidates", lambda candidates: candidates)
    monkeypatch.setattr(inspect_runner, "attach_warnings", lambda evaluations, element, detail: None)
    monkeypatch.setattr(inspect_runner, "build_code_snippet", lambda backend, target_window, evaluations: "")

    result = inspect_runner.run_inspect(
        Namespace(delay=0, timeout=12, backend="both", detail=False, scope="window", only_visible=False, max_items=None),
        point_selector=lambda: (10, 20),
    )

    lines = capsys.readouterr().out.splitlines()
    assert result == 0
    for backend in ["win32", "uia"]:
        assert f"[INFO] {backend}: セレクター候補の評価が完了しました。ヒット候補: 1件" in lines
        assert f"[INFO] {backend}: セレクター候補の再評価が完了しました。ヒット候補: 1件" in lines


def test_inspect_log_file_omits_cursor_line(monkeypatch, capsys):
    saved = []

    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: None)
    monkeypatch.setattr(inspect_runner, "get_cursor_position", lambda: CursorPosition(10, 20))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: SuccessfulInspector(backend))
    monkeypatch.setattr(inspect_runner, "save_inspection_log", lambda result, content, **kwargs: saved.append(content))

    result = inspect_runner.run_inspect(
        Namespace(delay=0, timeout=12, backend="win32", detail=False, scope="window", only_visible=False, max_items=None),
        point_selector=lambda: (10, 20),
    )

    assert result == 0
    assert saved
    assert saved[0].startswith("[Target Window]")
    assert "[INFO] 座標を決定しました。" not in saved[0]
    assert "[INFO] 座標を決定しました。 X=10, Y=20" in capsys.readouterr().out


def test_inspect_json_outputs_structured_data_without_info(monkeypatch, capsys):
    saved = []

    candidate = SelectorCandidate(
        backend="win32",
        selector_text='dlg.child_window(class_name="Button")',
        selector_kind="win32_class_name",
        condition={"class_name": "Button"},
    )
    evaluations = [SelectorEvaluation(candidate=candidate, hits=1, warnings=["ambiguous text"])]

    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: SuccessfulInspector(backend))
    monkeypatch.setattr(inspect_runner, "generate_candidates", lambda element, hierarchy: [candidate])
    monkeypatch.setattr(inspect_runner, "evaluate_candidates", lambda *args, **kwargs: evaluations)
    monkeypatch.setattr(inspect_runner, "append_found_index_candidates", lambda candidates, evaluations, element: candidates)
    monkeypatch.setattr(inspect_runner, "sort_candidates", lambda candidates: candidates)
    monkeypatch.setattr(inspect_runner, "deduplicate_candidates", lambda candidates: candidates)
    monkeypatch.setattr(inspect_runner, "attach_warnings", lambda evaluations, element, detail: None)
    monkeypatch.setattr(inspect_runner, "build_code_snippet", lambda backend, target_window, evaluations: "print('ok')")
    monkeypatch.setattr(inspect_runner, "save_inspection_log", lambda result, content, **kwargs: saved.append((content, kwargs)))

    result = inspect_runner.run_inspect(
        Namespace(delay=0, timeout=12, backend="win32", detail=False, scope="window", only_visible=False, max_items=None, json=True),
        point_selector=lambda: (10, 20),
    )

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert result == 0
    assert "[INFO]" not in output
    assert payload["cursor_position"] == {"x": 10, "y": 20}
    assert payload["backends"][0]["backend"] == "win32"
    assert payload["backends"][0]["selector_candidates"][0]["hits"] == 1
    assert json.loads(saved[0][0]) == payload
    assert saved[0][1]["suffix"] == ".json"


def test_inspect_adds_parent_found_index_fallback_when_no_single_hit(monkeypatch, capsys):
    base_candidate = SelectorCandidate(
        backend="uia",
        selector_text='dlg.child_window(title="開く", control_type="Button")',
        selector_kind="uia_title_control_type",
        condition={"title": "開く", "control_type": "Button"},
    )
    fallback_candidate = SelectorCandidate(
        backend="uia",
        selector_text='dlg.child_window(class_name="#32770", found_index=1).child_window(class_name="Button")',
        selector_kind="uia_parent_class_name_found_index_target_class_name",
        condition={"class_name": "Button"},
        uses_found_index=True,
        uses_parent_scope=True,
    )
    include_fallback_flags = []
    evaluated_counts = []

    def fake_generate_candidates(element, hierarchy, found_index_trial_count=None, include_parent_found_index_fallback=False):
        include_fallback_flags.append(include_parent_found_index_fallback)
        return [base_candidate, fallback_candidate] if include_parent_found_index_fallback else [base_candidate]

    def fake_evaluate_candidates(candidates, *args, **kwargs):
        evaluated_counts.append(len(candidates))
        return [
            SelectorEvaluation(candidate=candidate, hits=1 if candidate is fallback_candidate else 2)
            for candidate in candidates
        ]

    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: None)
    monkeypatch.setattr(inspect_runner, "get_cursor_position", lambda: CursorPosition(10, 20))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: SuccessfulInspector(backend))
    monkeypatch.setattr(inspect_runner, "generate_candidates", fake_generate_candidates)
    monkeypatch.setattr(inspect_runner, "evaluate_candidates", fake_evaluate_candidates)
    monkeypatch.setattr(inspect_runner, "append_found_index_candidates", lambda candidates, evaluations, element: candidates)
    monkeypatch.setattr(inspect_runner, "attach_warnings", lambda evaluations, element, detail: None)
    monkeypatch.setattr(inspect_runner, "build_code_snippet", lambda backend, target_window, evaluations: "")

    result = inspect_runner.run_inspect(
        Namespace(delay=0, timeout=12, backend="uia", detail=False, scope="window", only_visible=False, max_items=None),
        point_selector=lambda: (10, 20),
    )

    capsys.readouterr()
    assert result == 0
    assert include_fallback_flags == [False, True]
    assert evaluated_counts == [1, 2]


def test_failed_parent_found_index_trial_is_excluded_from_results():
    candidate = SelectorCandidate(
        backend="win32",
        selector_text='dlg.child_window(class_name="ReBarWindow32", found_index=2).child_window(class_name="ToolbarWindow32")',
        selector_kind="win32_parent_class_name_found_index_target_class_name",
        condition={"class_name": "ToolbarWindow32"},
        uses_found_index=True,
        uses_parent_scope=True,
    )
    evaluation = SelectorEvaluation(candidate=candidate, hits=None, status="timeout")

    assert inspect_runner._exclude_unmatched_evaluations([evaluation]) == []


def test_failed_uia_parent_found_index_trial_is_excluded_from_results():
    candidate = SelectorCandidate(
        backend="uia",
        selector_text='dlg.child_window(class_name="ComboBox", found_index=2).child_window(auto_id="DropDown", control_type="Button")',
        selector_kind="uia_parent_class_name_found_index_target_auto_id_control_type",
        condition={"auto_id": "DropDown", "control_type": "Button"},
        uses_found_index=True,
        uses_parent_scope=True,
    )
    evaluation = SelectorEvaluation(candidate=candidate, hits=None, status="timeout")

    assert inspect_runner._exclude_unmatched_evaluations([evaluation]) == []


def test_tree_backend_both_prints_win32_and_uia(monkeypatch, capsys):
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: TreeInspector(backend))

    result = inspect_runner.run_tree(
        Namespace(
            backend="both",
            cursor=False,
            window_title="電卓",
            title_re=False,
            depth=3,
            max_items=50,
            only_visible=True,
            detail=False,
            delay=0,
        )
    )

    output = capsys.readouterr().out
    assert result == 0
    assert output.count("[Tree]") == 1
    assert "  [Win32]" in output
    assert "  [UIA]" in output


def test_tree_logs_progress_messages(monkeypatch, capsys):
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: TreeInspector(backend))

    result = inspect_runner.run_tree(
        Namespace(
            backend="uia",
            cursor=False,
            window_title="電卓",
            title_re=False,
            depth=3,
            max_items=50,
            only_visible=True,
            detail=False,
            delay=0,
        )
    )

    lines = capsys.readouterr().out.splitlines()
    assert result == 0
    assert lines[:4] == [
        "[INFO] pyselector started",
        "[INFO] uia: 対象ウィンドウを検索中です...",
        "[INFO] uia: UI要素ツリーを取得中です... (depth=3, max-items=50)",
        "[INFO] uia: UI要素ツリー取得中... 1件完了",
    ]
    assert lines[4] == "[INFO] uia: UI要素ツリーの取得が完了しました。表示要素: 1件"


def test_tree_json_outputs_structured_data_without_info(monkeypatch, capsys):
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: TreeInspector(backend))

    result = inspect_runner.run_tree(
        Namespace(
            backend="uia",
            cursor=False,
            window_title="電卓",
            title_re=False,
            depth=3,
            max_items=50,
            only_visible=True,
            detail=False,
            delay=0,
            json=True,
        )
    )

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert result == 0
    assert "[INFO]" not in output
    assert payload["results"][0]["backend"] == "uia"
    assert payload["results"][0]["nodes"][0]["window_text"] == "電卓"


class HandleInspector:
    def __init__(self, backend):
        self.backend = backend
        self.handles = []
        self.points = []

    def element_from_point(self, x, y):
        self.points.append((x, y))
        return ElementInfo(backend=self.backend, window_text="from point", handle=1)

    def element_from_handle(self, handle):
        self.handles.append(handle)
        return ElementInfo(backend=self.backend, window_text="電卓", handle=handle)

    def get_target_window(self, element):
        # 座標から取得した要素はウィンドウの子要素、handle から取得した要素はウィンドウ自身とする。
        handle = element.handle if element.window_text == "電卓" else 999
        return TargetWindowInfo(backend=self.backend, title="電卓", handle=handle)

    def get_hierarchy(self, element):
        return []

    def find_elements(self, scope, condition):
        return [], False


def _inspect_args(**overrides):
    base = dict(
        delay=None,
        timeout=12,
        backend="win32",
        detail=False,
        scope="window",
        only_visible=False,
        max_items=None,
        at=None,
        handle=None,
    )
    base.update(overrides)
    return Namespace(**base)


def test_inspect_at_skips_overlay_and_countdown(monkeypatch, capsys):
    calls = []
    inspector = HandleInspector("win32")
    monkeypatch.setattr(inspect_runner, "select_point_with_overlay", lambda: calls.append("overlay") or (0, 0))
    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: calls.append("countdown"))
    monkeypatch.setattr(inspect_runner, "get_cursor_position", lambda: calls.append("cursor"))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    result = inspect_runner.run_inspect(_inspect_args(at=(636, 2240)))

    output = capsys.readouterr().out
    assert result == 0
    assert calls == []
    assert inspector.points == [(636, 2240)]
    assert "[INFO] 座標を決定しました。 X=636, Y=2240" in output


def test_inspect_handle_resolves_the_element_by_handle(monkeypatch, capsys):
    calls = []
    inspector = HandleInspector("win32")
    monkeypatch.setattr(inspect_runner, "select_point_with_overlay", lambda: calls.append("overlay") or (0, 0))
    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: calls.append("countdown"))
    monkeypatch.setattr(inspect_runner, "_window_center", lambda handle: (50, 60))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    result = inspect_runner.run_inspect(_inspect_args(handle=0x2E20F46, json=True))

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert calls == []
    assert inspector.handles == [0x2E20F46]
    assert inspector.points == []
    assert payload["cursor_position"] == {"x": 50, "y": 60}
    assert payload["backends"][0]["element"]["window_text"] == "電卓"


def test_inspect_handle_falls_back_to_a_window_only_snippet(monkeypatch, capsys):
    inspector = HandleInspector("win32")
    monkeypatch.setattr(inspect_runner, "_window_center", lambda handle: (50, 60))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    result = inspect_runner.run_inspect(_inspect_args(handle=100, json=True))

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["backends"][0]["selector_candidates"] == []
    assert payload["backends"][0]["code_snippet"] == (
        'from pywinauto import Desktop\n'
        'dlg = Desktop(backend="win32").window(title="電卓")\n'
        'dlg.wait("visible", timeout=10)'
    )


def test_inspect_child_element_without_candidates_keeps_a_null_snippet(monkeypatch, capsys):
    inspector = HandleInspector("win32")
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    result = inspect_runner.run_inspect(_inspect_args(at=(1, 2), json=True))

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["backends"][0]["code_snippet"] is None


def test_tree_uses_the_window_handle_when_given(monkeypatch, capsys):
    class HandleTreeInspector(TreeInspector):
        def __init__(self, backend):
            super().__init__(backend)
            self.handles = []

        def find_window_by_handle(self, handle):
            self.handles.append(handle)
            return ElementInfo(backend=self.backend, window_text="電卓", handle=handle)

    inspector = HandleTreeInspector("uia")
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: inspector)

    result = inspect_runner.run_tree(
        Namespace(
            backend="uia",
            cursor=False,
            window_title=None,
            window_handle=0x2E20F46,
            title_re=False,
            depth=3,
            max_items=50,
            only_visible=True,
            detail=False,
            delay=0,
            json=True,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert inspector.handles == [0x2E20F46]
    assert payload["results"][0]["nodes"][0]["window_text"] == "電卓"


def test_tree_progress_logger_reports_every_item(capsys):
    logger = inspect_runner._tree_progress_logger("uia", color=False)

    for done in range(1, 4):
        logger(done, 50)

    lines = capsys.readouterr().out.splitlines()
    assert lines == [
        "[INFO] uia: UI要素ツリー取得中... 1件完了",
        "[INFO] uia: UI要素ツリー取得中... 2件完了",
        "[INFO] uia: UI要素ツリー取得中... 3件完了",
    ]
