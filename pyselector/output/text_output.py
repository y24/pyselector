from __future__ import annotations

from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.inspection_result import BackendInspection, InspectionResult, TreeResult
from pyselector.model.selector_candidate import SelectorEvaluation
from pyselector.model.target_window import TargetWindowInfo
from pyselector.output.formatters import format_handle, format_rectangle, format_value, quote_text


def format_inspection_result(result: InspectionResult, detail: bool = False) -> str:
    lines: list[str] = [f"[INFO] cursor position: X={result.cursor_position.x}, Y={result.cursor_position.y}", ""]
    target = _first_target(result)
    lines.extend(format_target_window(target).splitlines())
    lines.append("")
    for inspection in _ordered_inspections(result):
        lines.extend(format_backend_element(inspection).splitlines())
        lines.append("")
    for inspection in _ordered_inspections(result):
        lines.extend(format_hierarchy(inspection.backend, inspection.hierarchy, detail, inspection.status, inspection.message).splitlines())
        lines.append("")
    for inspection in _ordered_inspections(result):
        lines.extend(format_selector_candidates(inspection.backend, inspection.evaluations).splitlines())
        lines.append("")
    for inspection in _ordered_inspections(result):
        if inspection.code_snippet:
            lines.extend(format_code_snippet(inspection.backend, inspection.code_snippet).splitlines())
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def format_backend_element(inspection: BackendInspection) -> str:
    label = "Win32" if inspection.backend == "win32" else "UIA"
    if inspection.status != "success" or inspection.element is None:
        return f"[{label} Backend]\n  status: failed\n  message: {format_value(inspection.message)}"
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
        ("process_id", element.process_id),
        ("process_name", element.process_name),
    ]
    return "\n".join([f"[{label} Backend]"] + [f"  {name}: {format_value(value)}" for name, value in fields])


def format_target_window(target_window: TargetWindowInfo | None) -> str:
    return "\n".join(
        [
            "[Target Window]",
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
) -> str:
    label = "Win32" if backend == "win32" else "UIA"
    lines = [f"[Hierarchy - {label}]"]
    if status != "success":
        lines.extend(["  status: failed", f"  message: {format_value(message)}"])
        return "\n".join(lines)
    if not nodes:
        lines.append("  status: no hierarchy")
        return "\n".join(lines)
    for node in nodes:
        kind = node.control_type or node.class_name or "Element"
        attrs = []
        if node.automation_id:
            attrs.append(f'auto_id="{node.automation_id}"')
        if node.class_name:
            attrs.append(f'class_name="{node.class_name}"')
        if node.control_id is not None:
            attrs.append(f"control_id={node.control_id}")
        if detail:
            if node.handle is not None:
                attrs.append(f"handle={format_handle(node.handle)}")
            if node.rectangle is not None:
                attrs.append(f"rectangle={format_rectangle(node.rectangle)}")
        suffix = ("  " + " ".join(attrs)) if attrs else ""
        lines.append(f"  {node.depth} {kind:<7} {quote_text(node.window_text)}{suffix}")
    return "\n".join(lines)


def format_selector_candidates(backend: str, evaluations: list[SelectorEvaluation]) -> str:
    label = "Win32" if backend == "win32" else "UIA"
    lines = [f"[Selector Candidates - {label}]"]
    if not evaluations:
        lines.append("  status: no candidates")
        return "\n".join(lines)
    lines.append("")
    for index, evaluation in enumerate(evaluations, 1):
        lines.append(f"[{index}] hits: {_format_hits(evaluation)}")
        lines.append(f"    {evaluation.candidate.selector_text}")
        for warning in evaluation.warnings:
            lines.append(f"    warning: {warning}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_code_snippet(backend: str, snippet: str) -> str:
    label = "Win32" if backend == "win32" else "UIA"
    return f"[Code Snippet - {label}]\n{snippet}"


def format_tree_result(result: TreeResult, detail: bool = False) -> str:
    label = "Win32" if result.backend == "win32" else "UIA"
    if result.status != "success":
        return f"[Tree - {label}]\n  status: failed\n  message: {format_value(result.message)}\n"
    lines = [f"[Tree - {label}]"]
    for node in result.nodes:
        kind = node.control_type or node.class_name or "Element"
        attrs = []
        if node.class_name:
            attrs.append(f'class_name="{node.class_name}"')
        if node.automation_id:
            attrs.append(f'auto_id="{node.automation_id}"')
        if node.control_id is not None:
            attrs.append(f"control_id={node.control_id}")
        if detail and node.rectangle is not None:
            attrs.append(f"rectangle={format_rectangle(node.rectangle)}")
        suffix = ("  " + " ".join(attrs)) if attrs else ""
        lines.append(f"  {node.depth} {kind:<7} {quote_text(node.window_text)}{suffix}")
    if result.reached_limit:
        lines.append("[WARN] max-items に達したため、以降の要素表示を省略しました。")
    return "\n".join(lines) + "\n"


def _format_hits(evaluation: SelectorEvaluation) -> str:
    if evaluation.status == "timeout":
        return "(Timeout)"
    if evaluation.status == "error":
        return "(Error)"
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
