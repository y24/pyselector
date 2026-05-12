from pyselector.model.element_info import ElementInfo
from pyselector.model.inspection_result import CursorPosition
from pyselector.model.rectangle import RectangleInfo
from pyselector.model.selector_candidate import SelectorCandidate, SelectorStep
from pyselector.backends.common import PywinautoInspectorMixin
from pyselector.selector.evaluator import evaluate_candidates


class FakeInspector:
    def __init__(self):
        self.steps = None

    def find_elements_chain(self, scope, steps, max_items):
        self.steps = steps
        return [ElementInfo(backend="win32", class_name="Edit")], False, 1


class ReachedLimitInspector:
    def find_elements(self, scope, condition):
        return [ElementInfo(backend="win32", class_name="Button") for _ in range(10)], True


class SlowInspector:
    def find_elements(self, scope, condition):
        import time

        time.sleep(0.01)
        return [], False


def test_evaluate_parent_scoped_candidate_uses_steps():
    inspector = FakeInspector()
    candidate = SelectorCandidate(
        backend="win32",
        selector_text='dlg.child_window(class_name="ComboBox").child_window(class_name="Edit")',
        selector_kind="win32_parent_class_name_target_class_name",
        condition={"class_name": "Edit"},
        steps=[
            SelectorStep(role="ancestor", condition={"class_name": "ComboBox"}),
            SelectorStep(role="target", condition={"class_name": "Edit"}),
        ],
        uses_parent_scope=True,
    )

    evaluations = evaluate_candidates([candidate], inspector, {}, timeout_sec=1, max_items=None)

    assert evaluations[0].hits == 1
    assert evaluations[0].parent_hits == 1
    assert inspector.steps == [
        {"class_name": "ComboBox"},
        {"class_name": "Edit"},
    ]


def test_found_index_candidate_does_not_inherit_limit_warning_when_found():
    candidate = SelectorCandidate(
        backend="win32",
        selector_text='dlg.child_window(class_name="Button", found_index=1)',
        selector_kind="win32_class_name_found_index",
        condition={"class_name": "Button", "found_index": 1},
        uses_found_index=True,
    )

    evaluations = evaluate_candidates([candidate], ReachedLimitInspector(), {}, timeout_sec=1, max_items=10)

    assert evaluations[0].hits == 1
    assert evaluations[0].reached_limit is False


def test_evaluate_candidates_stops_after_first_timeout():
    candidates = [
        SelectorCandidate(
            backend="win32",
            selector_text=f'dlg.child_window(class_name="Button", found_index={index})',
            selector_kind="win32_class_name_found_index",
            condition={"class_name": "Button", "found_index": index},
            uses_found_index=True,
        )
        for index in range(5)
    ]

    evaluations = evaluate_candidates(candidates, SlowInspector(), {}, timeout_sec=0, max_items=None)

    assert len(evaluations) == 1
    assert evaluations[0].status == "timeout"


class ChainWrapper:
    def __init__(self, class_name, children=None):
        self.element_info = type("ElementInfo", (), {"class_name": class_name, "name": ""})()
        self._class_name = class_name
        self._children = children or []

    def class_name(self):
        return self._class_name

    def window_text(self):
        return ""

    def control_id(self):
        return None

    def children(self):
        return self._children

    def descendants(self, **condition):
        matches = []
        for child in self._children:
            if child._class_name == condition.get("class_name"):
                matches.append(child)
            matches.extend(child.descendants(**condition))
        return matches

    def child_window(self, **condition):
        matches = self.descendants(**{key: value for key, value in condition.items() if key != "found_index"})
        found_index = condition.get("found_index", 0)
        return matches[found_index]

    def wrapper_object(self):
        return self


class DescendantsOnlyChainWrapper(ChainWrapper):
    def child_window(self, **condition):
        raise AssertionError("child_window() should not be called")


class ChainInspector(PywinautoInspectorMixin):
    backend_name = "win32"

    def __init__(self, root):
        super().__init__()
        self.root = root

    def _scope_root(self, scope):
        return self.root


def test_find_elements_chain_applies_found_index_to_intermediate_step():
    edit = ChainWrapper("Edit")
    root = ChainWrapper("Root", [ChainWrapper("ComboBox"), ChainWrapper("ComboBox", [edit])])
    inspector = ChainInspector(root)

    matches, reached_limit, parent_hits = inspector.find_elements_chain(
        {},
        [{"class_name": "ComboBox", "found_index": 1}, {"class_name": "Edit"}],
        None,
    )

    assert len(matches) == 1
    assert matches[0].class_name == "Edit"
    assert reached_limit is False
    assert parent_hits == 1


def test_find_elements_chain_resolves_found_index_candidate():
    edit = ChainWrapper("Edit")
    root = ChainWrapper("Root", [ChainWrapper("ComboBox"), ChainWrapper("ComboBox", [edit])])
    inspector = ChainInspector(root)

    matches, reached_limit, parent_hits = inspector.find_elements_chain(
        {},
        [{"class_name": "ComboBox", "found_index": 1}, {"class_name": "Edit"}],
        None,
    )

    assert len(matches) == 1
    assert matches[0].class_name == "Edit"
    assert reached_limit is False
    assert parent_hits == 1


def test_find_elements_chain_with_found_index_uses_descendants_without_child_window():
    edit = DescendantsOnlyChainWrapper("Edit")
    root = DescendantsOnlyChainWrapper(
        "Root",
        [
            DescendantsOnlyChainWrapper("ComboBox"),
            DescendantsOnlyChainWrapper("ComboBox", [edit]),
        ],
    )
    inspector = ChainInspector(root)

    matches, reached_limit, parent_hits = inspector.find_elements_chain(
        {},
        [{"class_name": "ComboBox", "found_index": 1}, {"class_name": "Edit"}],
        None,
    )

    assert len(matches) == 1
    assert matches[0].class_name == "Edit"
    assert reached_limit is False
    assert parent_hits == 1


class SequencedChainInspector:
    def __init__(self, use_rectangles=False):
        self.calls = 0
        self.use_rectangles = use_rectangles

    def find_elements_chain(self, scope, steps, max_items):
        self.calls += 1
        found_index = steps[0].get("found_index")
        if self.use_rectangles:
            rectangle = RectangleInfo(left=818, top=1175, right=1022, bottom=1191) if found_index == 1 else None
            return [ElementInfo(backend="win32", class_name="Edit", handle=100 + found_index, rectangle=rectangle)], False, 1
        if found_index == 1:
            return [ElementInfo(backend="win32", class_name="Edit", handle=200)], False, 1
        return [ElementInfo(backend="win32", class_name="Edit", handle=100 + found_index)], False, 1


def test_evaluate_found_index_candidates_require_target_match_and_stop_after_first_match():
    inspector = SequencedChainInspector()
    candidates = [
        SelectorCandidate(
            backend="win32",
            selector_text=f'dlg.child_window(class_name="ComboBox", found_index={index}).child_window(class_name="Edit")',
            selector_kind="win32_parent_class_name_found_index_target_class_name",
            condition={"class_name": "Edit"},
            steps=[
                SelectorStep(role="ancestor", condition={"class_name": "ComboBox", "found_index": index}),
                SelectorStep(role="target", condition={"class_name": "Edit"}),
            ],
            uses_found_index=True,
            uses_parent_scope=True,
        )
        for index in range(3)
    ]

    evaluations = evaluate_candidates(
        candidates,
        inspector,
        {},
        timeout_sec=1,
        max_items=None,
        target=ElementInfo(backend="win32", class_name="Edit", handle=200),
        stop_after_first_found_index_match=True,
    )

    assert [evaluation.hits for evaluation in evaluations] == [0, 1]
    assert inspector.calls == 2


def test_evaluate_found_index_candidates_accept_cursor_containing_rectangle():
    inspector = SequencedChainInspector(use_rectangles=True)
    candidates = [
        SelectorCandidate(
            backend="win32",
            selector_text=f'dlg.child_window(class_name="ComboBox", found_index={index}).child_window(class_name="Edit")',
            selector_kind="win32_parent_class_name_found_index_target_class_name",
            condition={"class_name": "Edit"},
            steps=[
                SelectorStep(role="ancestor", condition={"class_name": "ComboBox", "found_index": index}),
                SelectorStep(role="target", condition={"class_name": "Edit"}),
            ],
            uses_found_index=True,
            uses_parent_scope=True,
        )
        for index in range(3)
    ]

    evaluations = evaluate_candidates(
        candidates,
        inspector,
        {},
        timeout_sec=1,
        max_items=None,
        target=ElementInfo(backend="win32", class_name="Edit", handle=200),
        cursor_position=CursorPosition(x=900, y=1180),
        stop_after_first_found_index_match=True,
    )

    assert [evaluation.hits for evaluation in evaluations] == [0, 1]
    assert inspector.calls == 2


def test_evaluate_uia_parent_found_index_candidates_stop_after_first_match():
    inspector = SequencedChainInspector()
    candidates = [
        SelectorCandidate(
            backend="uia",
            selector_text=(
                f'dlg.child_window(class_name="ComboBox", found_index={index})'
                '.child_window(auto_id="DropDown", control_type="Button")'
            ),
            selector_kind="uia_parent_class_name_found_index_target_auto_id_control_type",
            condition={"auto_id": "DropDown", "control_type": "Button"},
            steps=[
                SelectorStep(role="ancestor", condition={"class_name": "ComboBox", "found_index": index}),
                SelectorStep(role="target", condition={"auto_id": "DropDown", "control_type": "Button"}),
            ],
            uses_found_index=True,
            uses_parent_scope=True,
        )
        for index in range(3)
    ]

    evaluations = evaluate_candidates(
        candidates,
        inspector,
        {},
        timeout_sec=1,
        max_items=None,
        target=ElementInfo(backend="uia", automation_id="DropDown", control_type="Button", handle=200),
        stop_after_first_found_index_match=True,
    )

    assert [evaluation.hits for evaluation in evaluations] == [0, 1]
    assert inspector.calls == 2
