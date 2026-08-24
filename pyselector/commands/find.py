from __future__ import annotations

from argparse import Namespace
from typing import Callable

from pyselector.commands import common
from pyselector.commands.common import (
    _build_backend_inspection,
    _element_center,
    _find_progress_logger,
    _info_logger,
    _matches_find_predicates,
    _resolve_backends,
    _resolve_find_root,
    _selector_options_from_args,
    _sort_find_elements,
    _use_color,
)
from pyselector.model.find_result import FindMatch, FindResult
from pyselector.output.json_output import format_find_results_json
from pyselector.output.text_output import format_find_result
from pyselector.utils.errors import StaleRefError
from pyselector.utils.logging import info_log
from pyselector.wait import DEFAULT_POLL_INTERVAL, poll_until

def run_find(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    common.setup_dpi_awareness()

    with_state = getattr(args, "with_state", False)
    backends = _resolve_backends(args.backend, getattr(args, "ref", None))

    def attempt() -> list[FindResult]:
        return search_elements(
            args,
            log,
            backends=backends,
            with_selectors=getattr(args, "with_selectors", False),
            with_state=with_state,
            progress=None if json_output else color,
        )

    results, outcome = poll_until(
        attempt,
        _find_wait_predicate(args),
        timeout=getattr(args, "wait", None) or getattr(args, "wait_gone", None),
        poll_interval=getattr(args, "poll_interval", DEFAULT_POLL_INTERVAL),
    )
    if outcome.attempts > 1:
        log(f"待機しました。{outcome.rounded}秒 / {outcome.attempts}回")

    compact = getattr(args, "compact", False)
    output = (
        format_find_results_json(results, compact=compact, with_state=with_state, outcome=outcome)
        if json_output
        else "".join(
            format_find_result(result, args.detail, color, include_heading=index == 0)
            for index, result in enumerate(results)
        )
    )
    print(output, end="")
    if not any(result.status == "success" for result in results):
        return 1
    return 0 if any(result.matches for result in results) else 1


def _find_wait_predicate(args: Namespace) -> Callable[[list[FindResult]], bool]:
    """待機の打ち切り条件。

    ``--wait`` はどれかの backend が一致を得たら終わり、``--wait-gone`` は
    すべての backend が 0 件になったら終わり。どちらも指定が無ければ、
    最初の 1 回で必ず終わる。
    """
    if getattr(args, "wait_gone", None):
        return lambda results: not any(result.matches for result in results)
    if getattr(args, "wait", None):
        return lambda results: any(result.matches for result in results)
    return lambda results: True


def search_elements(
    args: Namespace,
    log: Callable[[str], None],
    backends: list[str],
    with_selectors: bool = False,
    with_state: bool = False,
    progress: bool | None = None,
    inspectors: dict[str, object] | None = None,
) -> list[FindResult]:
    """条件に一致する要素を backend ごとに集める。

    find と expect が共有する。状態の読み取りは ``--limit`` を適用した後に行い、
    走査した全要素ではなく出力する要素だけを対象にする（設計 11 §3.2）。

    ``inspectors`` を渡すと、使った inspector を backend ごとに書き戻す。要素の
    内部参照は inspector が保持しているため、あとで同じ要素を扱う処理（記録など）は
    必ずこれと同じ inspector を使う必要がある。作り直すと参照表が空になる。
    """
    options = _selector_options_from_args(args)
    results: list[FindResult] = []
    for backend in backends:
        inspector = common._create_inspector(backend)
        if inspectors is not None:
            inspectors[backend] = inspector
        try:
            root = _resolve_find_root(inspector, backend, args, log)
            log(f"{backend}: 要素を走査中です... (depth={args.depth}, max-items={args.max_items})")
            elements, reached_limit = inspector.walk_elements(
                root,
                args.depth,
                args.max_items,
                args.only_visible,
                _find_progress_logger(backend, progress) if progress is not None else None,
            )
            matched = _sort_find_elements([element for element in elements if _matches_find_predicates(element, args)])
            log(f"{backend}: 走査が完了しました。走査 {len(elements)}件 / 一致 {len(matched)}件")
            total_matched = len(matched)
            limit = getattr(args, "limit", None)
            truncated = limit is not None and total_matched > limit
            matched = matched[:limit] if limit is not None else matched
            if with_state:
                matched = [inspector.read_element_state(element) for element in matched]
            matches: list[FindMatch] = []
            for index, element in enumerate(matched):
                inspection = None
                if with_selectors and index < args.selector_limit:
                    inspection = _build_backend_inspection(
                        backend,
                        inspector,
                        element,
                        _element_center(element),
                        options,
                        log,
                    )
                matches.append(FindMatch(element=element, inspection=inspection))
            results.append(
                FindResult(
                    backend=backend,
                    root=root,
                    matches=matches,
                    scanned=len(elements),
                    total_matched=total_matched,
                    reached_limit=reached_limit,
                    truncated=truncated,
                )
            )
        except StaleRefError:
            raise
        except Exception as exc:
            results.append(FindResult(backend=backend, status="failed", message=str(exc)))
    return results
