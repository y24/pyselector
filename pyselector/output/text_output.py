from __future__ import annotations

from collections import Counter

from pyselector.model.act_result import ActResult
from pyselector.model.diff_result import BackendDiff
from pyselector.model.element_info import ElementInfo
from pyselector.model.find_result import FindMatch, FindResult
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.inspection_result import BackendInspection, InspectionResult, TreeResult
from pyselector.model.selector_candidate import SelectorEvaluation
from pyselector.model.target_window import TargetWindowInfo
from pyselector.model.window_summary import WindowsResult
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
        suffix = ("  " + ", ".join(attrs)) if attrs else ""
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


def format_tree_result(
    result: TreeResult,
    detail: bool = False,
    color: bool = False,
    include_heading: bool = True,
    summary: bool = False,
) -> str:
    label = _backend_label(result.backend)
    if result.status != "success":
        lines = _tree_header_lines(label, color, include_heading)
        lines.extend(["    status: failed", f"    message: {format_value(result.message)}"])
        return "\n".join(lines) + "\n"
    if summary:
        lines = _tree_header_lines(label, color, include_heading)
        lines.extend(_tree_summary_lines(result))
        return "\n".join(lines) + "\n"
    lines = _tree_header_lines(label, color, include_heading)
    for node in result.nodes:
        kind = node.control_type or node.class_name or "Element"
        attrs = _hierarchy_attrs(result.backend, node)
        if detail and node.rectangle is not None:
            attrs.append(f"rectangle={format_rectangle(node.rectangle)}")
        suffix = ("  " + ", ".join(attrs)) if attrs else ""
        lines.append(f"    {node.depth} {kind:<7} {quote_text(node.window_text)}{suffix}")
    if result.reached_limit:
        lines.append("[WARN] max-items に達したため、以降の要素表示を省略しました。")
    return "\n".join(lines) + "\n"


def _tree_summary_lines(result: TreeResult) -> list[str]:
    control_types = Counter(node.control_type for node in result.nodes if node.control_type)
    class_names = Counter(node.class_name for node in result.nodes if node.class_name)
    lines = [
        f"    total: {len(result.nodes)}",
        f"    max_depth: {max((node.depth for node in result.nodes), default=0)}",
        f"    reached_limit: {result.reached_limit}",
    ]
    lines.extend(_counter_lines("by_control_type", control_types))
    lines.extend(_counter_lines("by_class_name", class_names))
    return lines


def _counter_lines(title: str, counter: Counter) -> list[str]:
    if not counter:
        return []
    lines = [f"    {title}:"]
    for name, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"      {name}: {count}")
    return lines


def format_windows_result(result: WindowsResult, color: bool = False, include_heading: bool = True) -> str:
    lines: list[str] = []
    if include_heading:
        lines.append(_heading("Windows", color, level=1))
    lines.append(_heading(_backend_label(result.backend), color, level=2))
    if result.status != "success":
        lines.extend(["    status: failed", f"    message: {format_value(result.message)}"])
        return "\n".join(lines) + "\n"
    if not result.windows:
        lines.append("    status: no windows")
        return "\n".join(lines) + "\n"
    for window in result.windows:
        attrs = [f'class_name="{window.class_name}"'] if window.class_name else []
        if window.process_name:
            attrs.append(f'process_name="{window.process_name}"')
        if window.process_id is not None:
            attrs.append(f"process_id={window.process_id}")
        suffix = ("  " + ", ".join(attrs)) if attrs else ""
        lines.append(f"    {format_handle(window.handle)} {quote_text(window.title)}{suffix}")
    if result.reached_limit:
        lines.append("[WARN] max-items に達したため、以降のウィンドウ表示を省略しました。")
    return "\n".join(lines) + "\n"


def format_find_result(
    result: FindResult,
    detail: bool = False,
    color: bool = False,
    include_heading: bool = True,
) -> str:
    lines: list[str] = []
    if include_heading:
        lines.append(_heading("Find", color, level=1))
    lines.append(_heading(_backend_label(result.backend), color, level=2))
    if result.status != "success":
        lines.extend(["    status: failed", f"    message: {format_value(result.message)}"])
        return "\n".join(lines) + "\n"
    lines.append(f"    scanned: {result.scanned}, matched: {result.total_matched}")
    if not result.matches:
        lines.append("    status: no matches")
        return "\n".join(lines) + "\n"
    for match in result.matches:
        lines.extend(_find_match_lines(result.backend, match, detail, color))
    if result.truncated:
        lines.append("[WARN] limit に達したため、以降の一致要素表示を省略しました。")
    if result.reached_limit:
        lines.append("[WARN] max-items に達したため、走査を打ち切りました。")
    return "\n".join(lines) + "\n"


def _find_match_lines(backend: str, match: FindMatch, detail: bool, color: bool) -> list[str]:
    element = match.element
    kind = element.control_type or element.class_name or "Element"
    attrs = []
    point = match.point
    if point is not None:
        attrs.append(f"point={point[0]},{point[1]}")
    if backend == "uia" and element.control_type:
        attrs.append(f'control_type="{element.control_type}"')
    if element.automation_id:
        attrs.append(f'auto_id="{element.automation_id}"')
    if element.class_name:
        attrs.append(f'class_name="{element.class_name}"')
    if element.handle is not None:
        attrs.append(f"handle={format_handle(element.handle)}")
    if detail and element.rectangle is not None:
        attrs.append(f"rectangle={format_rectangle(element.rectangle)}")
    suffix = ("  " + ", ".join(attrs)) if attrs else ""
    depth = element.depth if element.depth is not None else 0
    lines = [f"    {depth} {kind:<7} {quote_text(element.window_text)}{suffix}"]
    if match.inspection is not None:
        lines.extend(_find_inspection_lines(match.inspection, color))
    return lines


def _find_inspection_lines(inspection: BackendInspection, color: bool) -> list[str]:
    lines = [f"      {_heading('Selector Candidates', color, level=2).strip()}"]
    evaluations = [evaluation for evaluation in inspection.evaluations if evaluation.hits != 0]
    if not evaluations:
        lines.append("        status: no candidates")
    for evaluation in evaluations:
        lines.append(f"        [{_format_hits(evaluation)}] {evaluation.candidate.selector_text}")
        for warning in evaluation.warnings:
            lines.append(f"            - warning: {warning}")
    if inspection.code_snippet:
        lines.append(f"      {_heading('Code Snippet', color, level=2).strip()}")
        lines.extend(f"      {line}" for line in inspection.code_snippet.splitlines())
    return lines


def format_act_result(result: ActResult, color: bool = False) -> str:
    lines = [_heading("Act", color, level=1)]
    lines.append(_heading(_backend_label(result.backend), color, level=2))
    lines.append(f"    action: {result.action}" + (f" (value={result.value!r})" if result.value is not None else ""))
    if result.dry_run:
        lines.append("    performed: False (dry-run)")
    else:
        lines.append(f"    performed: {result.performed}")
        lines.append(f"    method: {format_value(result.method)}")
    point = result.point
    lines.append(f"    point: {f'{point[0]},{point[1]}' if point is not None else '(None)'}")
    if result.target_window is not None:
        lines.append(f"    window: {quote_text(result.target_window.title)}")
    if result.target is not None:
        lines.append(f"    target: {quote_text(result.target.window_text)}  {_element_attrs(result.target)}")
    if result.element_after is not None and result.target is not None:
        after = result.element_after
        if after.window_text != result.target.window_text:
            lines.append(f"    after: {quote_text(after.window_text)}")
    if result.diff is not None:
        lines.append("")
        lines.extend(format_diff_result(result.diff, color, include_heading=True).rstrip("\n").splitlines())
    return "\n".join(lines) + "\n"


def _element_attrs(element: ElementInfo) -> str:
    attrs = []
    if element.control_type:
        attrs.append(f'control_type="{element.control_type}"')
    if element.automation_id:
        attrs.append(f'auto_id="{element.automation_id}"')
    if element.class_name:
        attrs.append(f'class_name="{element.class_name}"')
    return ", ".join(attrs)


def format_diff_result(diff: BackendDiff, color: bool = False, include_heading: bool = True) -> str:
    lines: list[str] = []
    if include_heading:
        lines.append(_heading("Diff", color, level=1))
    lines.append(_heading(_backend_label(diff.backend), color, level=2))
    if diff.status != "success":
        lines.extend(["    status: failed", f"    message: {format_value(diff.message)}"])
        return "\n".join(lines) + "\n"
    lines.append(
        f"    added: {len(diff.added)}, removed: {len(diff.removed)}, "
        f"changed: {len(diff.changed)}, unchanged: {diff.unchanged}"
    )
    if not diff.has_differences:
        lines.append("    status: no differences")
        return "\n".join(lines) + "\n"
    for label, nodes in (("+", diff.added), ("-", diff.removed)):
        for node in nodes:
            lines.append(f"    {label} {_diff_node_line(node)}")
    for change in diff.changed:
        lines.append(f"    ~ {_diff_node_line(change.after)}")
        for field, values in change.changes.items():
            lines.append(f"        {field}: {values['before']!r} -> {values['after']!r}")
    return "\n".join(lines) + "\n"


def _diff_node_line(node: dict) -> str:
    kind = node.get("control_type") or node.get("class_name") or "Element"
    attrs = []
    if node.get("automation_id"):
        attrs.append(f'auto_id="{node["automation_id"]}"')
    if node.get("class_name"):
        attrs.append(f'class_name="{node["class_name"]}"')
    suffix = ("  " + ", ".join(attrs)) if attrs else ""
    return f'{node.get("depth")} {kind:<7} {quote_text(node.get("window_text"))}{suffix}'


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
