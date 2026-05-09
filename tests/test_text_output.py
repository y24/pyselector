from pyselector.model.element_info import ElementInfo
from pyselector.model.inspection_result import BackendInspection, CursorPosition, InspectionResult
from pyselector.model.rectangle import RectangleInfo
from pyselector.output.text_output import format_inspection_result


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
