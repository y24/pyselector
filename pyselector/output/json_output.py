from __future__ import annotations

import json
from collections import Counter

from pyselector.model.act_result import ActResult
from pyselector.model.diff_result import BackendDiff
from pyselector.model.element_info import ElementInfo
from pyselector.model.expect_result import ExpectResult
from pyselector.model.find_result import FindMatch, FindResult
from pyselector.model.hierarchy import HierarchyNode
from pyselector.model.inspection_result import BackendInspection, InspectionResult, TreeResult
from pyselector.model.lifecycle_result import CloseResult, LaunchResult
from pyselector.model.rectangle import RectangleInfo
from pyselector.model.selector_candidate import SelectorCandidate, SelectorEvaluation, SelectorStep
from pyselector.model.target_window import TargetWindowInfo
from pyselector.model.window_summary import WindowSummary, WindowsResult
from pyselector.record.model import Recording, RecordedStep
from pyselector.server import session
from pyselector.wait import WaitOutcome

#: v2 で全コマンドのエンベロープに served が現れ、サーバー経由時は要素に ref が付く。
#: v1 の上位互換で、既存キーの削除・改名はしていない（設計 10）。
SCHEMA_VERSION = 2


def format_inspection_result_json(result: InspectionResult) -> str:
    inspections = _ordered_inspections(result)
    return _dump(
        _envelope(
            "inspect",
            _overall_status(inspections),
            {
                "cursor_position": {"x": result.cursor_position.x, "y": result.cursor_position.y},
                "target_window": _target_window_to_dict(_first_target(result)),
                "backends": [_backend_inspection_to_dict(inspection) for inspection in inspections],
            },
        )
    )


def format_tree_results_json(results: list[TreeResult], summary: bool = False, compact: bool = False) -> str:
    return _dump(
        _envelope(
            "tree",
            _overall_status(results),
            {"results": [_tree_result_to_dict(result, summary, compact) for result in results]},
        )
    )


def format_windows_results_json(results: list[WindowsResult], compact: bool = False) -> str:
    return _dump(
        _envelope(
            "windows",
            _overall_status(results),
            {"results": [_windows_result_to_dict(result, compact) for result in results]},
        )
    )


def format_find_results_json(
    results: list[FindResult],
    compact: bool = False,
    with_state: bool = False,
    outcome: WaitOutcome | None = None,
) -> str:
    payload: dict[str, object] = {
        "results": [_find_result_to_dict(result, compact, with_state) for result in results]
    }
    payload.update(_wait_to_dict(outcome))
    return _dump(_envelope("find", _overall_status(results), payload))


def _wait_to_dict(outcome: WaitOutcome | None) -> dict[str, object]:
    """待った実績。1 回で決まったのか粘ったのかが、生成コードの timeout の根拠になる。"""
    if outcome is None:
        return {}
    return {"waited": outcome.rounded, "attempts": outcome.attempts, "timed_out": outcome.timed_out}


def format_launch_result_json(result: LaunchResult, recorded: RecordedStep | None = None) -> str:
    return _dump(
        _envelope(
            "launch",
            result.status,
            {
                "exe": result.exe,
                "args": list(result.args),
                "window_title_re": result.window_title_re,
                "timeout": result.timeout,
                "dry_run": result.dry_run,
                "attached": result.attached,
                "pid": result.pid,
                "backend": result.backend,
                "window": _element_to_dict(result.window),
                "target_window": _target_window_to_dict(result.target_window),
                "recorded": _recorded_to_dict(recorded),
            },
        )
    )


def format_close_result_json(result: CloseResult, recorded: RecordedStep | None = None) -> str:
    return _dump(
        _envelope(
            "close",
            result.status,
            {
                "performed": result.performed,
                "dry_run": result.dry_run,
                "forced": result.forced,
                "method": result.method,
                "backend": result.backend,
                "window": _element_to_dict(result.window),
                "target_window": _target_window_to_dict(result.target_window),
                "recorded": _recorded_to_dict(recorded),
            },
        )
    )


def format_recording_json(
    command: str,
    recording: Recording | None,
    extra: dict[str, object] | None = None,
) -> str:
    payload: dict[str, object] = {
        "recording": recording.to_dict() if recording is not None else None,
        "steps": len(recording.steps) if recording is not None else 0,
    }
    payload.update(extra or {})
    return _dump(_envelope(command, "success", payload))


def _recorded_to_dict(step: RecordedStep | None) -> dict[str, object] | None:
    """記録された手順の要約。何が残ったかをその場で確認できるようにする。"""
    if step is None:
        return None
    return {
        "seq": step.seq,
        "kind": step.kind,
        "action": step.action,
        "selector": step.selector.to_dict() if step.selector else None,
        "selector_warning": step.selector_warning,
    }


def format_expect_result_json(
    result: ExpectResult,
    compact: bool = False,
    outcome: WaitOutcome | None = None,
    recorded: RecordedStep | None = None,
) -> str:
    """判定の結果を返す。

    satisfied は「判定が成立したか」、status は「判定を実行できたか」であり、
    別の軸である。0 件と失敗を分けるのと同じ考え方（設計 11 §6.3）。
    """
    return _dump(
        _envelope(
            "expect",
            result.status,
            {
                "satisfied": result.satisfied,
                "expectation": {
                    "kind": result.expectation.kind,
                    "expected": result.expectation.expected,
                    "actual": result.expectation.actual,
                },
                "matched": result.matched,
                "message": result.message,
                "results": [
                    _find_result_to_dict(item, compact, with_state=True) for item in result.results
                ],
                **_wait_to_dict(outcome),
                "recorded": _recorded_to_dict(recorded),
            },
        )
    )


def format_act_result_json(
    result: ActResult,
    outcome: WaitOutcome | None = None,
    recorded: RecordedStep | None = None,
) -> str:
    point = result.point
    payload: dict[str, object] = {
        "action": result.action,
        "value": result.value,
        "performed": result.performed,
        "dry_run": result.dry_run,
        "method": result.method,
        "backend": result.backend,
        "target_window": _target_window_to_dict(result.target_window),
        "point": {"x": point[0], "y": point[1]} if point is not None else None,
        "target": _element_to_dict(result.target, with_state=True),
        "element_after": _element_to_dict(result.element_after, with_state=True),
    }
    if outcome is not None:
        payload["settle"] = {
            "waited": outcome.rounded,
            "attempts": outcome.attempts,
            "timed_out": outcome.timed_out,
        }
    payload["recorded"] = _recorded_to_dict(recorded)
    if result.diff is not None:
        payload["diff"] = _backend_diff_to_dict(result.diff)
    return _dump(_envelope("act", result.status, payload))


def format_diff_results_json(diffs: list[BackendDiff], compact: bool = False) -> str:
    return _dump(
        _envelope(
            "diff",
            _overall_status(diffs),
            {"results": [_backend_diff_to_dict(diff, compact) for diff in diffs]},
        )
    )


def _backend_diff_to_dict(diff: BackendDiff, compact: bool = False) -> dict[str, object]:
    return {
        "backend": diff.backend,
        "status": diff.status,
        "message": diff.message,
        "has_differences": diff.has_differences,
        "summary": {
            "added": len(diff.added),
            "removed": len(diff.removed),
            "changed": len(diff.changed),
            "unchanged": diff.unchanged,
        },
        "added": [_diff_node_to_dict(node, compact) for node in diff.added],
        "removed": [_diff_node_to_dict(node, compact) for node in diff.removed],
        "changed": [
            {
                "node": _diff_node_to_dict(change.after, compact),
                "changes": change.changes,
            }
            for change in diff.changed
        ],
    }


def _diff_node_to_dict(node: dict[str, object], compact: bool = False) -> dict[str, object]:
    if not compact:
        return node
    return {key: node.get(key) for key in ("depth", "window_text", "control_type", "automation_id", "class_name")}


def format_version_json(version: str) -> str:
    return _dump(_envelope("version", "success", {"version": version}))


def format_error_json(command: str | None, code: str, exit_code: int, message: str) -> str:
    return _dump(
        _envelope(
            command or "unknown",
            "error",
            {"error": {"code": code, "exit_code": exit_code, "message": message}},
        )
    )


def _envelope(command: str, status: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "status": status,
        "served": session.is_serving(),
        **payload,
    }


def _overall_status(results: list) -> str:
    if not results:
        return "error"
    return "success" if any(getattr(result, "status", "success") == "success" for result in results) else "error"


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _backend_inspection_to_dict(inspection: BackendInspection) -> dict[str, object]:
    return {
        "backend": inspection.backend,
        "status": inspection.status,
        "message": inspection.message,
        "target_window": _target_window_to_dict(inspection.target_window),
        "element": _element_to_dict(inspection.element, with_state=True),
        "hierarchy": [hierarchy_node_to_dict(node) for node in inspection.hierarchy],
        "selector_candidates": [_selector_evaluation_to_dict(evaluation) for evaluation in inspection.evaluations],
        "code_snippet": inspection.code_snippet,
    }


def _tree_result_to_dict(result: TreeResult, summary: bool = False, compact: bool = False) -> dict[str, object]:
    payload: dict[str, object] = {
        "backend": result.backend,
        "status": result.status,
        "message": result.message,
        "root": _element_to_dict(result.root, compact),
        "reached_limit": result.reached_limit,
    }
    if summary:
        payload["summary"] = _tree_summary(result.nodes)
    else:
        payload["nodes"] = [hierarchy_node_to_dict(node, compact) for node in result.nodes]
    return payload


def _tree_summary(nodes: list[HierarchyNode]) -> dict[str, object]:
    control_types = Counter(node.control_type for node in nodes if node.control_type)
    class_names = Counter(node.class_name for node in nodes if node.class_name)
    return {
        "total": len(nodes),
        "max_depth": max((node.depth for node in nodes), default=0),
        "by_control_type": dict(sorted(control_types.items(), key=lambda item: (-item[1], item[0]))),
        "by_class_name": dict(sorted(class_names.items(), key=lambda item: (-item[1], item[0]))),
    }


def _windows_result_to_dict(result: WindowsResult, compact: bool = False) -> dict[str, object]:
    return {
        "backend": result.backend,
        "status": result.status,
        "message": result.message,
        "reached_limit": result.reached_limit,
        "windows": [_window_summary_to_dict(window, compact) for window in result.windows],
    }


def _window_summary_to_dict(window: WindowSummary, compact: bool = False) -> dict[str, object]:
    if compact:
        return {
            "title": window.title,
            "class_name": window.class_name,
            "process_name": window.process_name,
            "handle": window.handle,
        }
    return {
        "backend": window.backend,
        "title": window.title,
        "class_name": window.class_name,
        "process_name": window.process_name,
        "process_id": window.process_id,
        "handle": window.handle,
        "rectangle": _rectangle_to_dict(window.rectangle),
        "is_visible": window.is_visible,
        "is_enabled": window.is_enabled,
    }


def _find_result_to_dict(
    result: FindResult,
    compact: bool = False,
    with_state: bool = False,
) -> dict[str, object]:
    return {
        "backend": result.backend,
        "status": result.status,
        "message": result.message,
        "root": _element_to_dict(result.root, compact),
        "scanned": result.scanned,
        "total_matched": result.total_matched,
        "reached_limit": result.reached_limit,
        "truncated": result.truncated,
        "matches": [_find_match_to_dict(match, compact, with_state) for match in result.matches],
    }


def _find_match_to_dict(
    match: FindMatch,
    compact: bool = False,
    with_state: bool = False,
) -> dict[str, object]:
    point = match.point
    payload: dict[str, object] = {
        "point": {"x": point[0], "y": point[1]} if point is not None else None,
        "depth": match.element.depth,
        "handle": match.element.handle,
        "element": _element_to_dict(match.element, compact, with_state),
    }
    if match.inspection is not None:
        payload["inspection"] = _backend_inspection_to_dict(match.inspection)
    return payload


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


def _element_to_dict(
    element: ElementInfo | None,
    compact: bool = False,
    with_state: bool = False,
) -> dict[str, object] | None:
    if element is None:
        return None
    if compact:
        payload = {
            "window_text": element.window_text,
            "control_type": element.control_type,
            "automation_id": element.automation_id,
            "class_name": element.class_name,
        }
        return _with_ref(payload, element)
    payload = {
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
    if with_state:
        # state を読んだときだけ現れる。読んでいないのに null が並ぶと、
        # 「取得できなかった」と「読んでいない」が区別できなくなる。
        payload["state"] = _element_state_to_dict(element)
    return _with_ref(payload, element)


def _element_state_to_dict(element: ElementInfo) -> dict[str, object]:
    return {
        "value": element.value,
        "is_checked": element.is_checked,
        "is_selected": element.is_selected,
        "is_offscreen": element.is_offscreen,
        "has_keyboard_focus": element.has_keyboard_focus,
    }


def _with_ref(payload: dict[str, object], element: ElementInfo) -> dict[str, object]:
    """サーバー経由のときだけ ref を載せる。

    ローカル実行の ref はプロセス終了とともに消えるので、出力すると
    「後から使えるはず」と誤解させる（設計 7.2）。
    """
    if session.is_serving() and element.ref is not None:
        payload["ref"] = element.ref
    return payload


def hierarchy_node_to_dict(node: HierarchyNode, compact: bool = False) -> dict[str, object]:
    if compact:
        return {
            "depth": node.depth,
            "window_text": node.window_text,
            "control_type": node.control_type,
            "automation_id": node.automation_id,
            "class_name": node.class_name,
        }
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
