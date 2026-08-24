from __future__ import annotations

import time
from argparse import Namespace

from pyselector.commands import common
from pyselector.commands.common import (
    _info_logger,
    _resolve_backends,
    _tree_progress_logger,
    _use_color,
)
from pyselector.model.inspection_result import TreeResult
from pyselector.output.json_output import format_tree_results_json
from pyselector.output.text_output import format_tree_result
from pyselector.utils.errors import StaleRefError
from pyselector.utils.logging import info_log

def run_tree(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    common.setup_dpi_awareness()
    ref = getattr(args, "ref", None)
    backends = _resolve_backends(args.backend, ref)
    cursor = None
    if args.cursor:
        if json_output:
            time.sleep(args.delay)
        else:
            common.wait_with_countdown(args.delay, color)
        cursor = common.get_cursor_position()
        log(f"座標を決定しました。 X={cursor.x}, Y={cursor.y}")

    window_handle = getattr(args, "window_handle", None)
    results: list[TreeResult] = []
    for backend in backends:
        inspector = common._create_inspector(backend)
        try:
            if ref is not None:
                log(f"{backend}: ref {ref} の起点要素を取得中です...")
                root = inspector.element_from_ref(ref)
            elif cursor is not None:
                log(f"{backend}: カーソル下の起点要素を取得中です...")
                root = inspector.element_from_point(cursor.x, cursor.y)
            elif window_handle is not None:
                log(f"{backend}: handle {window_handle:#x} のウィンドウを取得中です...")
                root = inspector.find_window_by_handle(window_handle)
            else:
                log(f"{backend}: 対象ウィンドウを検索中です...")
                root = inspector.find_window_by_title(args.window_title, args.title_re)
            log(f"{backend}: UI要素ツリーを取得中です... (depth={args.depth}, max-items={args.max_items})")
            nodes, reached_limit = inspector.walk_tree(
                root,
                args.depth,
                args.max_items,
                args.only_visible,
                None if json_output else _tree_progress_logger(backend, color),
            )
            log(f"{backend}: UI要素ツリーの取得が完了しました。表示要素: {len(nodes)}件")
            results.append(
                TreeResult(
                    backend=backend,
                    root=root,
                    nodes=nodes,
                    reached_limit=reached_limit,
                )
            )
        except StaleRefError:
            raise
        except Exception as exc:
            results.append(
                TreeResult(
                    backend=backend,
                    root=None,
                    nodes=[],
                    reached_limit=False,
                    status="failed",
                    message=str(exc),
                )
            )
    summary = getattr(args, "summary", False)
    compact = getattr(args, "compact", False)
    output = (
        format_tree_results_json(results, summary=summary, compact=compact)
        if json_output
        else "".join(
            format_tree_result(result, args.detail, color, include_heading=index == 0, summary=summary)
            for index, result in enumerate(results)
        )
    )
    print(output, end="")
    return 0 if any(result.status == "success" for result in results) else 1
