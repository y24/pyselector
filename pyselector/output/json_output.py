from __future__ import annotations

import json

from pyselector.model.element_info import ElementInfo
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.inspection_result import BackendInspection, InspectionResult, TreeResult
from pyselector.model.rectangle import RectangleInfo
from pyselector.model.selector_candidate import SelectorCandidate, SelectorEvaluation, SelectorStep
from pyselector.model.target_window import TargetWindowInfo


def format_inspection_result_json(result: InspectionResult) -> str:
    return _dump(
        {
            "cursor_position": {"x": result.cursor_position.x, "y": result.cursor_position.y},
            "target_window": _target_window_to_dict(_first_target(result)),
            "backends": [_backend_inspection_to_dict(inspection) for inspection in _ordered_inspections(result)],
        }
    )


def format_tree_results_json(results: list[TreeResult]) -> str:
    return _dump({"results": [_tree_result_to_dict(result) for result in results]})


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _backend_inspection_to_dict(inspection: BackendInspection) -> dict[str, object]:
    return {
        "backend": inspection.backend,
        "status": inspection.status,
        "message": inspection.message,
        "target_window": _target_window_to_dict(inspection.target_window),
        "element": _element_to_dict(inspection.element),
        "hierarchy": [_hierarchy_node_to_dict(node) for node in inspection.hierarchy],
        "selector_candidates": [_selector_evaluation_to_dict(evaluation) for evaluation in inspection.evaluations],
        "code_snippet": inspection.code_snippet,
    }


def _tree_result_to_dict(result: TreeResult) -> dict[str, object]:
    return {
        "backend": result.backend,
        "status": result.status,
        "message": result.message,
        "root": _element_to_dict(result.root),
        "nodes": [_hierarchy_node_to_dict(node) for node in result.nodes],
        "reached_limit": result.reached_limit,
    }


def _target_window_to_dict(target_window: TargetWindowInfo | None) -> dict[str, object] | None:
    if target_window is None:
        return None
    return {
        "backend": target_window.backend,
        "title": target_window.title,
        "class_name": target_window.class_name,
        "process_name": target_window.process_name,
        "process_id": target_window.process_id,
        "handle": target_window.handle,
    }


def _element_to_dict(element: ElementInfo | None) -> dict[str, object] | None:
    if element is None:
        return None
    return {
        "backend": element.backend,
        "window_text": element.window_text,
        "control_type": element.control_type,
        "automation_id": element.automation_id,
        "class_name": element.class_name,
        "friendly_class_name": element.friendly_class_name,
        "control_id": element.control_id,
        "children_count": element.children_count,
        "depth": element.depth,
        "rectangle": _rectangle_to_dict(element.rectangle),
        "is_visible": element.is_visible,
        "is_enabled": element.is_enabled,
        "handle": element.handle,
        "process_id": element.process_id,
        "process_name": element.process_name,
    }


def _hierarchy_node_to_dict(node: HierarchyNode) -> dict[str, object]:
    return {
        "depth": node.depth,
        "window_text": node.window_text,
        "control_type": node.control_type,
        "automation_id": node.automation_id,
        "class_name": node.class_name,
        "friendly_class_name": node.friendly_class_name,
        "control_id": node.control_id,
        "handle": node.handle,
        "rectangle": _rectangle_to_dict(node.rectangle),
    }


def _rectangle_to_dict(rectangle: RectangleInfo | None) -> dict[str, int] | None:
    if rectangle is None:
        return None
    return {
        "left": rectangle.left,
        "top": rectangle.top,
        "right": rectangle.right,
        "bottom": rectangle.bottom,
        "width": rectangle.width,
        "height": rectangle.height,
    }


def _selector_evaluation_to_dict(evaluation: SelectorEvaluation) -> dict[str, object]:
    return {
        "selector_text": evaluation.candidate.selector_text,
        "selector_kind": evaluation.candidate.selector_kind,
        "hits": evaluation.hits,
        "status": evaluation.status,
        "warnings": evaluation.warnings,
        "reached_limit": evaluation.reached_limit,
        "parent_hits": evaluation.parent_hits,
        "error_message": evaluation.error_message,
        "candidate": _selector_candidate_to_dict(evaluation.candidate),
    }


def _selector_candidate_to_dict(candidate: SelectorCandidate) -> dict[str, object]:
    return {
        "backend": candidate.backend,
        "selector_text": candidate.selector_text,
        "selector_kind": candidate.selector_kind,
        "condition": candidate.condition,
        "steps": [_selector_step_to_dict(step) for step in candidate.steps],
        "uses_title": candidate.uses_title,
        "uses_title_re": candidate.uses_title_re,
        "uses_class_name": candidate.uses_class_name,
        "uses_control_id": candidate.uses_control_id,
        "uses_auto_id": candidate.uses_auto_id,
        "uses_control_type": candidate.uses_control_type,
        "uses_found_index": candidate.uses_found_index,
        "uses_parent_scope": candidate.uses_parent_scope,
        "display_order": candidate.display_order,
    }


def _selector_step_to_dict(step: SelectorStep) -> dict[str, object]:
    return {"role": step.role, "condition": step.condition}


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
