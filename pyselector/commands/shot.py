from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from typing import Any

from pyselector import screenshot
from pyselector.commands import common
from pyselector.commands.common import _info_logger, _use_color
from pyselector.commands.find import search_elements
from pyselector.model.element_info import ElementInfo
from pyselector.model.shot_result import Annotation, ShotResult
from pyselector.output.json_output import format_shot_result_json
from pyselector.output.text_output import format_shot_result
from pyselector.server.refs import ref_backend
from pyselector.utils.logging import info_log


def run_shot(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    common.setup_dpi_awareness()

    ref = getattr(args, "ref", None)
    backend = ref_backend(ref) if ref is not None else args.backend
    inspector = common._create_inspector(backend)

    if getattr(args, "screen", False):
        log("画面全体を撮ります...")
        image, origin = screenshot.capture_screen()
        target = None
    else:
        target = _resolve_target(inspector, backend, args, log)
        log(f"{backend}: 画像を取得中です...")
        image, origin = screenshot.capture_wrapper(inspector._wrapper_for(target), target.rectangle)

    annotations: list[Annotation] = []
    if getattr(args, "annotate", False):
        annotations = _annotations(args, log, backend)
        if annotations:
            log(f"{backend}: {len(annotations)}件に注釈を描き込みます...")
            image = screenshot.annotate(
                image, origin, [(item.index, item.element.rectangle) for item in annotations if item.element.rectangle]
            )

    path = screenshot.save(image, Path(args.out), getattr(args, "force", False))
    log(f"保存しました: {path}")

    result = ShotResult(
        backend=backend,
        path=str(path),
        width=image.width,
        height=image.height,
        origin=origin,
        target=target,
        annotations=annotations,
    )
    output = format_shot_result_json(result) if json_output else format_shot_result(result, color)
    print(output, end="")
    return 0


def _resolve_target(inspector: Any, backend: str, args: Namespace, log) -> ElementInfo:
    ref = getattr(args, "ref", None)
    if ref is not None:
        log(f"{backend}: ref {ref} の要素を取得中です...")
        return inspector.element_from_ref(ref)
    at = getattr(args, "at", None)
    if at is not None:
        log(f"{backend}: 座標 X={at[0]}, Y={at[1]} の要素を取得中です...")
        return inspector.element_from_point(at[0], at[1])
    if getattr(args, "window_handle", None) is not None:
        log(f"{backend}: handle {args.window_handle:#x} のウィンドウを取得中です...")
        return inspector.find_window_by_handle(args.window_handle)
    log(f"{backend}: 対象ウィンドウを検索中です...")
    return inspector.find_window_by_title(args.window_title, getattr(args, "title_re", False))


def _annotations(args: Namespace, log, backend: str) -> list[Annotation]:
    """注釈をつける要素を find と同じ条件で集める。

    番号は 1 始まり。JSON に番号と要素の対応を載せるので、画像を見た側は
    「3 番のボタン」という形で対象を指せる。
    """
    results = search_elements(args, log, backends=[backend])
    matches = results[0].matches if results and results[0].status == "success" else []
    return [
        Annotation(index=index, element=match.element)
        for index, match in enumerate(matches, start=1)
        if match.element.rectangle is not None
    ]
