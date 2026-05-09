from pyselector.model.element_info import ElementInfo
from pyselector.model.selector_candidate import SelectorCandidate, SelectorStep
from pyselector.selector.evaluator import evaluate_candidates


class FakeInspector:
    def __init__(self):
        self.steps = None

    def find_elements_chain(self, scope, steps, max_items):
        self.steps = steps
        return [ElementInfo(backend="win32", class_name="Edit")], False, 1


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
