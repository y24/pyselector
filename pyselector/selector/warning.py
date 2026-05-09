from __future__ import annotations

from pyselector.model.element_info import ElementInfo
from pyselector.model.selector_candidate import SelectorEvaluation

FOUND_INDEX_WARNING = "found_index は画面構成や表示順の変更に弱い可能性があります"


def attach_warnings(evaluations: list[SelectorEvaluation], element: ElementInfo, detail: bool = False) -> list[SelectorEvaluation]:
    for evaluation in evaluations:
        evaluation.warnings = build_warnings(evaluation, element, detail)
    return evaluations


def build_warnings(evaluation: SelectorEvaluation, element: ElementInfo, detail: bool = False) -> list[str]:
    warnings: list[str] = []
    if evaluation.status == "error":
        warnings.append("セレクター評価に失敗しました")
    if evaluation.status == "timeout":
        warnings.append("セレクター評価がタイムアウトしました")
    if evaluation.hits == 0:
        warnings.append("この候補では対象要素にヒットしません")
    if evaluation.hits is not None and evaluation.hits > 1:
        warnings.append("複数要素にヒットします")
    if evaluation.candidate.uses_found_index:
        warnings.append(FOUND_INDEX_WARNING)
    if evaluation.reached_limit:
        warnings.append("探索上限に達したため、ヒット件数が実際より少ない可能性があります")
    if element.is_visible is False:
        warnings.append("対象要素は非表示です")
    if element.is_enabled is False:
        warnings.append("対象要素は無効状態です")
    if detail and (evaluation.candidate.uses_title or evaluation.candidate.uses_title_re):
        warnings.append("title/window_text は表示文言変更の影響を受ける可能性があります")
    return warnings
