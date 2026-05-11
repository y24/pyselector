from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.inspection_result import BackendInspection, CursorPosition, InspectionResult, TreeResult
from pyselector.model.rectangle import RectangleInfo
from pyselector.model.selector_candidate import SelectorCandidate, SelectorEvaluation
from pyselector.model.target_window import TargetWindowInfo
from pyselector.output.text_output import format_hierarchy, format_inspection_result, format_selector_candidates
from pyselector.output.text_output import format_tree_result


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

    assert output.startswith("[INFO] 座標を決定しました。 X=10, Y=20")
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
    assert output.startswith("\033[90m[INFO] 座標を決定しました。 X=10, Y=20\033[0m")


def test_inspection_output_can_omit_cursor_line():
    result = InspectionResult(
        cursor_position=CursorPosition(10, 20),
        win32=BackendInspection(backend="win32", element=ElementInfo(backend="win32")),
    )

    output = format_inspection_result(result, include_cursor=False)

    assert not output.startswith("[INFO] cursor position")
    assert output.startswith("[Target Window]")


def test_backend_output_omits_process_fields_from_element_info():
    element = ElementInfo(backend="win32", process_id=12345, process_name="sample.exe")
    target_window = TargetWindowInfo(backend="win32", process_id=12345, process_name="sample.exe")
    result = InspectionResult(
        cursor_position=CursorPosition(10, 20),
        win32=BackendInspection(backend="win32", element=element, target_window=target_window),
    )

    output = format_inspection_result(result)
    target_section = output.split("[Backend]", 1)[0]
    backend_section = output.split("[Backend]", 1)[1].split("[Hierarchy]", 1)[0]

    assert "  process_name: sample.exe" in target_section
    assert "  process_id: 12345" in target_section
    assert "process_name" not in backend_section
    assert "process_id" not in backend_section


def test_hierarchy_output_omits_control_id_and_shows_uia_control_type():
    win32_nodes = [
        HierarchyNode(depth=0, window_text="OK", class_name="Button", control_id=1, control_type="Button"),
    ]
    uia_nodes = [
        HierarchyNode(depth=0, window_text="OK", class_name="Button", control_id=1, control_type="Button"),
    ]

    win32_output = format_hierarchy("win32", win32_nodes, detail=False)
    uia_output = format_hierarchy("uia", uia_nodes, detail=False)

    assert "control_id=1" not in win32_output
    assert "control_id=1" not in uia_output
    assert 'control_type="Button"' not in win32_output
    assert 'control_type="Button"' in uia_output


def test_hierarchy_output_shows_friendly_class_name_only_when_different():
    nodes = [
        HierarchyNode(depth=0, class_name="Button", friendly_class_name="Button"),
        HierarchyNode(depth=1, class_name="AfxWnd", friendly_class_name="Custom Control"),
    ]

    output = format_hierarchy("win32", nodes, detail=False)

    assert '0 Button' in output
    assert 'friendly_class_name="Button"' not in output
    assert 'friendly_class_name="Custom Control"' in output


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
            selector_text='dlg.child_window(class_name="Button")',
            selector_kind="win32_class_name",
            condition={"class_name": "Button"},
        ),
        hits=4,
        warnings=["複数要素にヒットします"],
    )

    output = format_selector_candidates("win32", [candidate])

    assert '    [4] dlg.child_window(class_name="Button")' in output
    assert "        - warning: 複数要素にヒットします" in output


def test_selector_candidates_output_marks_reached_limit_with_plus():
    candidate = SelectorEvaluation(
        candidate=SelectorCandidate(
            backend="win32",
            selector_text='dlg.child_window(class_name="Button")',
            selector_kind="win32_class_name",
            condition={"class_name": "Button"},
        ),
        hits=10,
        reached_limit=True,
    )

    output = format_selector_candidates("win32", [candidate])

    assert '    [10+] dlg.child_window(class_name="Button")' in output


def test_tree_output_shows_warnings():
    result = TreeResult(
        backend="win32",
        root=ElementInfo(backend="win32"),
        nodes=[HierarchyNode(depth=0, window_text="電卓", class_name="ApplicationFrameWindow")],
        reached_limit=False,
        warnings=["詳細なツリーは --backend uia --depth 5 を試してください。"],
    )

    output = format_tree_result(result)

    assert "[WARN] 詳細なツリーは --backend uia --depth 5 を試してください。" in output
