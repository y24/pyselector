from __future__ import annotations

from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.inspection_result import BackendInspection, InspectionResult, TreeResult
from pyselector.model.selector_candidate import SelectorEvaluation
from pyselector.model.target_window import TargetWindowInfo
from pyselector.output.formatters import format_handle, format_rectangle, format_value, quote_text
from pyselector.utils.logging import format_info

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
BRIGHT_BLUE = "\033[94m"


def format_inspection_result(
    result: InspectionResult,
    detail: bool = False,
    color: bool = False,
    include_cursor: bool = True,
) -> str:
    lines: list[str] = []
    if include_cursor:
        lines.extend([format_info(f"座標を決定しました。 X={result.cursor_position.x}, Y={result.cursor_position.y}", color), ""])
    target = _first_target(result)
    lines.extend(format_target_window(target, color).splitlines())
    lines.append("")
    lines.append(_heading("Backend", color, level=1))
    for inspection in _ordered_inspections(result):
        lines.extend(format_backend_element(inspection, color).splitlines())
        lines.append("")
    lines.append(_heading("Hierarchy", color, level=1))
    for inspection in _ordered_inspections(result):
        lines.extend(
            format_hierarchy(inspection.backend, inspection.hierarchy, detail, inspection.status, inspection.message, color).splitlines()
        )
        lines.append("")
    lines.append(_heading("Selector Candidates", color, level=1))
    for inspection in _ordered_inspections(result):
        lines.extend(format_selector_candidates(inspection.backend, inspection.evaluations, color).splitlines())
        lines.append("")
    snippets = [inspection for inspection in _ordered_inspections(result) if inspection.code_snippet]
    if snippets:
        lines.append(_heading("Code Snippet", color, level=1))
    for inspection in snippets:
        if inspection.code_snippet:
            lines.extend(format_code_snippet(inspection.backend, inspection.code_snippet, color).splitlines())
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_backend_element(inspection: BackendInspection, color: bool = False) -> str:
    label = _backend_label(inspection.backend)
    if inspection.status != "success" or inspection.element is None:
        return f"{_heading(label, color, level=2)}\n    status: failed\n    message: {format_value(inspection.message)}"
    element = inspection.element
    fields = [
        ("window_text", element.window_text),
        ("control_type", element.control_type),
        ("automation_id", element.automation_id),
        ("class_name", element.class_name),
        ("friendly_class_name", element.friendly_class_name),
        ("control_id", element.control_id),
        ("children_count", element.children_count),
        ("depth", element.depth),
        ("rectangle", format_rectangle(element.rectangle)),
        ("is_visible", element.is_visible),
        ("is_enabled", element.is_enabled),
        ("handle", format_handle(element.handle)),
    ]
    return "\n".join([_heading(label, color, level=2)] + [f"    {name}: {format_value(value)}" for name, value in fields])


def format_target_window(target_window: TargetWindowInfo | None, color: bool = False) -> str:
    return "\n".join(
        [
            _heading("Target Window", color, level=1),
            f"  title: {format_value(target_window.title if target_window else None)}",
            f"  class_name: {format_value(target_window.class_name if target_window else None)}",
            f"  process_name: {format_value(target_window.process_name if target_window else None)}",
            f"  process_id: {format_value(target_window.process_id if target_window else None)}",
            f"  handle: {format_handle(target_window.handle if target_window else None)}",
        ]
    )


def format_hierarchy(
    backend: str,
    nodes: list[HierarchyNode],
    detail: bool,
    status: str = "success",
    message: str | None = None,
    color: bool = False,
) -> str:
    lines = [_heading(_backend_label(backend), color, level=2)]
    if status != "success":
        lines.extend(["    status: failed", f"    message: {format_value(message)}"])
        return "\n".join(lines)
    if not nodes:
        lines.append("    status: no hierarchy")
        return "\n".join(lines)
    for node in nodes:
        kind = node.control_type or node.class_name or "Element"
        attrs = _hierarchy_attrs(backend, node)
        if detail:
            if node.handle is not None:
                attrs.append(f"handle={format_handle(node.handle)}")
            if node.rectangle is not None:
                attrs.append(f"rectangle={format_rectangle(node.rectangle)}")
        suffix = ("  " + " ".join(attrs)) if attrs else ""
        lines.append(f"    {node.depth} {kind:<7} {quote_text(node.window_text)}{suffix}")
    return "\n".join(lines)


def format_selector_candidates(backend: str, evaluations: list[SelectorEvaluation], color: bool = False) -> str:
    lines = [_heading(_backend_label(backend), color, level=2)]
    evaluations = [evaluation for evaluation in evaluations if evaluation.hits != 0]
    if not evaluations:
        lines.append("    status: no candidates")
        return "\n".join(lines)
    for evaluation in evaluations:
        lines.append(f"    [{_format_hits(evaluation)}] {evaluation.candidate.selector_text}")
        for warning in evaluation.warnings:
            lines.append(f"        - warning: {warning}")
    return "\n".join(lines).rstrip()


def format_code_snippet(backend: str, snippet: str, color: bool = False) -> str:
    return f"{_heading(_backend_label(backend), color, level=2)}\n{snippet}"


def format_tree_result(result: TreeResult, detail: bool = False, color: bool = False, include_heading: bool = True) -> str:
    label = _backend_label(result.backend)
    if result.status != "success":
        lines = _tree_header_lines(label, color, include_heading)
        lines.extend(["    status: failed", f"    message: {format_value(result.message)}"])
        return "\n".join(lines) + "\n"
    lines = _tree_header_lines(label, color, include_heading)
    for node in result.nodes:
        kind = node.control_type or node.class_name or "Element"
        attrs = _hierarchy_attrs(result.backend, node)
        if detail and node.rectangle is not None:
            attrs.append(f"rectangle={format_rectangle(node.rectangle)}")
        suffix = ("  " + " ".join(attrs)) if attrs else ""
        lines.append(f"    {node.depth} {kind:<7} {quote_text(node.window_text)}{suffix}")
    if result.reached_limit:
        lines.append("[WARN] max-items に達したため、以降の要素表示を省略しました。")
    return "\n".join(lines) + "\n"


def _tree_header_lines(label: str, color: bool, include_heading: bool) -> list[str]:
    lines = []
    if include_heading:
        lines.append(_heading("Tree", color, level=1))
    lines.append(_heading(label, color, level=2))
    return lines


def _heading(text: str, color: bool, level: int) -> str:
    heading = f"[{text}]"
    prefix = "  " if level == 2 else ""
    if not color:
        return f"{prefix}{heading}"
    style = f"{BOLD}{CYAN}" if level == 1 else BRIGHT_BLUE
    return f"{prefix}{style}{heading}{RESET}"


def _backend_label(backend: str) -> str:
    return "Win32" if backend == "win32" else "UIA"


def _hierarchy_attrs(backend: str, node: HierarchyNode) -> list[str]:
    attrs = []
    if backend == "uia" and node.control_type:
        attrs.append(f'control_type="{node.control_type}"')
    if node.automation_id:
        attrs.append(f'auto_id="{node.automation_id}"')
    if node.class_name:
        attrs.append(f'class_name="{node.class_name}"')
    if node.friendly_class_name and node.friendly_class_name != node.class_name:
        attrs.append(f'friendly_class_name="{node.friendly_class_name}"')
    return attrs


def _format_hits(evaluation: SelectorEvaluation) -> str:
    if evaluation.status == "timeout":
        return "(Timeout)"
    if evaluation.status == "error":
        return "(Error)"
    if evaluation.reached_limit:
        return f"{evaluation.hits}+"
    return str(evaluation.hits)


def _ordered_inspections(result: InspectionResult) -> list[BackendInspection]:
    inspections: list[BackendInspection] = []
    if result.win32 is not None:
        inspections.append(result.win32)
    if result.uia is not None:
        inspections.append(result.uia)
    return inspections


def _first_target(result: InspectionResult) -> TargetWindowInfo | None:
    for inspection in _ordered_inspections(result):
        if inspection.target_window is not None:
            return inspection.target_window
    return None
