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


def test_warning_for_handle_even_when_single_hit():
    element = ElementInfo(backend="win32", is_visible=True, is_enabled=True)
    candidate = SelectorCandidate(
        backend="win32",
        selector_text="dlg.child_window(handle=0x123456)",
        selector_kind="win32_handle",
        condition={"handle": 0x123456},
        uses_handle=True,
    )
    evaluation = SelectorEvaluation(candidate=candidate, hits=1)

    assert build_warnings(evaluation, element) == ["handle はアプリ起動ごとに変わる可能性があります"]
