from __future__ import annotations

import re
from argparse import Namespace

from pyselector.commands import common
from pyselector.commands.common import _info_logger, _resolve_backends, _use_color
from pyselector.model.element_info import ElementInfo
from pyselector.model.window_summary import WindowSummary, WindowsResult
from pyselector.output.json_output import format_windows_results_json
from pyselector.output.text_output import format_windows_result
from pyselector.utils.logging import info_log

def run_windows(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    common.setup_dpi_awareness()

    results: list[WindowsResult] = []
    for backend in _resolve_backends(args.backend):
        inspector = common._create_inspector(backend)
        try:
            log(f"{backend}: ウィンドウ一覧を取得中です...")
            elements = inspector.list_windows(args.only_visible)
            summaries = _filter_windows(_to_window_summaries(elements, backend), args)
            reached_limit = len(summaries) > args.max_items
            log(f"{backend}: ウィンドウ一覧の取得が完了しました。該当: {len(summaries)}件")
            results.append(
                WindowsResult(
                    backend=backend,
                    windows=summaries[: args.max_items],
                    reached_limit=reached_limit,
                )
            )
        except Exception as exc:
            results.append(WindowsResult(backend=backend, status="failed", message=str(exc)))

    compact = getattr(args, "compact", False)
    output = (
        format_windows_results_json(results, compact=compact)
        if json_output
        else "".join(
            format_windows_result(result, color, include_heading=index == 0)
            for index, result in enumerate(results)
        )
    )
    print(output, end="")
    if not any(result.status == "success" for result in results):
        return 1
    return 0 if any(result.windows for result in results) else 1


def _to_window_summaries(elements: list[ElementInfo], backend: str) -> list[WindowSummary]:
    return [
        WindowSummary(
            backend=backend,
            title=element.window_text,
            class_name=element.class_name,
            process_name=common.get_process_name(element.process_id),
            process_id=element.process_id,
            handle=element.handle,
            rectangle=element.rectangle,
            is_visible=element.is_visible,
            is_enabled=element.is_enabled,
        )
        for element in elements
    ]


def _filter_windows(windows: list[WindowSummary], args: Namespace) -> list[WindowSummary]:
    title = getattr(args, "title", None)
    title_re = getattr(args, "title_re", False)
    process = getattr(args, "process", None)
    pid = getattr(args, "pid", None)
    include_untitled = getattr(args, "include_untitled", False)
    filtered = []
    for window in windows:
        window_title = window.title or ""
        if not window_title and not include_untitled:
            continue
        if title is not None:
            if title_re:
                if re.search(title, window_title) is None:
                    continue
            elif title.casefold() not in window_title.casefold():
                continue
        if process is not None and process.casefold() not in (window.process_name or "").casefold():
            continue
        if pid is not None and window.process_id != pid:
            continue
        filtered.append(window)
    return filtered
