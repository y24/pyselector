from argparse import Namespace
from pathlib import Path

from pyselector import inspect_runner
from pyselector.model.element_info import ElementInfo
from pyselector.model.inspection_result import CursorPosition
from pyselector.model.selector_candidate import SelectorCandidate, SelectorEvaluation
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


class SuccessfulInspector:
    def __init__(self, backend):
        self.backend = backend

    def element_from_point(self, x, y):
        return ElementInfo(backend=self.backend)

    def get_target_window(self, element):
        return TargetWindowInfo(backend=self.backend, handle=100)

    def get_hierarchy(self, element):
        return []


def test_inspect_logs_timeout_before_countdown(monkeypatch, capsys):
    monkeypatch.setattr(inspect_runner, "wait_with_countdown", lambda delay, color=False: None)
    monkeypatch.setattr(inspect_runner, "get_cursor_position", lambda: CursorPosition(10, 20))
    monkeypatch.setattr(inspect_runner, "_create_inspector", lambda backend: FailingInspector())

    result = inspect_runner.run_inspect(
        Namespace(delay=5, timeout=12, backend="uia", detail=False, scope="window", only_visible=False, max_items=None)
    )

    lines = capsys.readouterr().out.splitlines()
    assert result == 1
    assert lines[:2] == [
        "[INFO] pyselector started",
        "[INFO] selector validation total timeout: 12 sec",
    ]
    assert "[INFO] selector hit count limit: 10" not in lines
    assert "[INFO] uia: カーソル下の要素を取得中です..." not in lines


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
        )
    )

    lines = capsys.readouterr().out.splitlines()
    assert result == 1
    assert lines[:3] == [
        "[INFO] pyselector started",
        "[INFO] pyselector_config.json loaded",
        "[INFO] selector validation total timeout: 12 sec",
    ]


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
        Namespace(delay=0, timeout=12, backend="both", detail=False, scope="window", only_visible=False, max_items=None)
    )

    lines = capsys.readouterr().out.splitlines()
    assert result == 0
    for backend in ["win32", "uia"]:
        assert f"[INFO] {backend}: セレクター候補の評価が完了しました。ヒット候補: 1件" in lines
        assert f"[INFO] {backend}: セレクター候補の再評価が完了しました。ヒット候補: 1件" in lines


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
        Namespace(delay=0, timeout=12, backend="uia", detail=False, scope="window", only_visible=False, max_items=None)
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
