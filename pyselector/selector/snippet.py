from __future__ import annotations

from pyselector.model.selector_candidate import SelectorEvaluation
from pyselector.model.target_window import TargetWindowInfo
from pyselector.utils.text import escape_python_string, is_blank


def build_code_snippet(
    backend: str,
    target_window: TargetWindowInfo | None,
    evaluations: list[SelectorEvaluation],
) -> str | None:
    candidate = choose_snippet_candidate(evaluations)
    if candidate is None:
        return None
    window_expr = _window_expression(backend, target_window)
    return f"from pywinauto import Desktop\n{window_expr}\ntarget = {candidate.candidate.selector_text}\ntarget.click()"


def choose_snippet_candidate(evaluations: list[SelectorEvaluation]) -> SelectorEvaluation | None:
    if not evaluations:
        return None
    for evaluation in evaluations:
        if evaluation.hits == 1 and not evaluation.warnings:
            return evaluation
    for evaluation in evaluations:
        if evaluation.hits == 1 and evaluation.warnings == ["found_index は画面構成や表示順の変更に弱い可能性があります"]:
            return evaluation
    return evaluations[0]


def _window_expression(backend: str, target_window: TargetWindowInfo | None) -> str:
    if target_window and not is_blank(target_window.title):
        return f'dlg = Desktop(backend="{backend}").window(title="{escape_python_string(target_window.title or "")}")'
    return f'dlg = Desktop(backend="{backend}").window()'
