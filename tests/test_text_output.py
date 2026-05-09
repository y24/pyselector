from pyselector.model.element_info import ElementInfo
from pyselector.model.inspection_result import BackendInspection, CursorPosition, InspectionResult
from pyselector.model.rectangle import RectangleInfo
from pyselector.model.selector_candidate import SelectorCandidate, SelectorEvaluation
from pyselector.output.text_output import format_inspection_result, format_selector_candidates


def test_inspection_output_contains_core_sections():
    element = ElementInfo(
        backend="win32",
        window_text="OK",
        class_name="Button",
        control_id=1,
        rectangle=RectangleInfo(1, 2, 11, 22),
        is_visible=True,
        is_enabled=True,
    )
    result = InspectionResult(
        cursor_position=CursorPosition(10, 20),
        win32=BackendInspection(backend="win32", element=element),
    )

    output = format_inspection_result(result)

    assert output.startswith("[INFO] cursor position: X=10, Y=20")
    assert "[Backend]" in output
    assert "  [Win32]" in output
    assert "    rectangle: L=1, T=2, R=11, B=22, W=10, H=20" in output
    assert "[Selector Candidates]" in output


def test_inspection_output_can_color_headings():
    result = InspectionResult(
        cursor_position=CursorPosition(10, 20),
        win32=BackendInspection(backend="win32", element=ElementInfo(backend="win32")),
    )

    output = format_inspection_result(result, color=True)

    assert "\033[1m\033[36m[Target Window]\033[0m" in output
    assert "\033[94m[Win32]\033[0m" in output


def test_selector_candidates_output_excludes_zero_hits():
    zero_hit = SelectorEvaluation(
        candidate=SelectorCandidate(
            backend="uia",
            selector_text='dlg.child_window(auto_id="Header", control_type="Text")',
            selector_kind="uia_auto_id_control_type",
            condition={"auto_id": "Header", "control_type": "Text"},
        ),
        hits=0,
        warnings=["この候補では対象要素にヒットしません"],
    )
    matched = SelectorEvaluation(
        candidate=SelectorCandidate(
            backend="uia",
            selector_text='dlg.child_window(control_type="Text")',
            selector_kind="uia_control_type",
            condition={"control_type": "Text"},
        ),
        hits=1,
    )

    output = format_selector_candidates("uia", [zero_hit, matched])

    assert 'dlg.child_window(auto_id="Header", control_type="Text")' not in output
    assert "この候補では対象要素にヒットしません" not in output
    assert '    [1] dlg.child_window(control_type="Text")' in output
    assert "        * hits:" not in output
    assert 'dlg.child_window(control_type="Text")' in output


def test_selector_candidates_output_uses_hits_as_prefix():
    candidate = SelectorEvaluation(
        candidate=SelectorCandidate(
            backend="win32",
            selector_text='dlg.child_window(control_id=0)',
            selector_kind="win32_control_id",
            condition={"control_id": 0},
        ),
        hits=4,
        warnings=["複数要素にヒットします"],
    )

    output = format_selector_candidates("win32", [candidate])

    assert '    [4] dlg.child_window(control_id=0)' in output
    assert "        - warning: 複数要素にヒットします" in output
