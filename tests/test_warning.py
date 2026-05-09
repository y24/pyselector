from pyselector.model.element_info import ElementInfo
from pyselector.model.selector_candidate import SelectorCandidate, SelectorEvaluation
from pyselector.selector.warning import build_warnings


def test_warning_for_multiple_hits_and_found_index():
    element = ElementInfo(backend="win32", is_visible=True, is_enabled=True)
    candidate = SelectorCandidate(
        backend="win32",
        selector_text='dlg.child_window(class_name="Button", found_index=3)',
        selector_kind="win32_class_name_found_index",
        condition={"class_name": "Button", "found_index": 3},
        uses_found_index=True,
    )
    evaluation = SelectorEvaluation(candidate=candidate, hits=5)

    warnings = build_warnings(evaluation, element)

    assert "複数要素にヒットします" in warnings
    assert "found_index は画面構成や表示順の変更に弱い可能性があります" in warnings


def test_warning_for_multiple_parent_hits():
    element = ElementInfo(backend="win32", is_visible=True, is_enabled=True)
    candidate = SelectorCandidate(
        backend="win32",
        selector_text='dlg.child_window(class_name="ComboBox").child_window(class_name="Edit")',
        selector_kind="win32_parent_class_name_target_class_name",
        condition={"class_name": "Edit"},
        uses_parent_scope=True,
    )
    evaluation = SelectorEvaluation(candidate=candidate, hits=1, parent_hits=2)

    warnings = build_warnings(evaluation, element)

    assert "親要素が複数ヒットします" in warnings

