from __future__ import annotations

import time
from argparse import Namespace
from typing import Callable

from pyselector.commands import common
from pyselector.commands.common import (
    _build_backend_inspection,
    _element_point,
    _find_backend,
    _info_logger,
    _resolve_backends,
    _selector_options_from_args,
    _use_color,
    OVERLAY_CLOSE_WAIT_SECONDS,
)
from pyselector.model.inspection_result import BackendInspection, CursorPosition, InspectionResult
from pyselector.output.json_output import format_inspection_result_json
from pyselector.output.log_file import save_inspection_log
from pyselector.output.text_output import format_inspection_result
from pyselector.overlay.selector_overlay import select_point_with_overlay
from pyselector.server.refs import ref_backend
from pyselector.utils.errors import StaleRefError
from pyselector.utils.logging import info_log

def run_inspect(args: Namespace, point_selector: Callable[[], tuple[int, int] | None] | None = None) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    log = _info_logger(json_output, color)
    if not json_output:
        info_log("pyselector started", color)
    config_path = getattr(args, "config_path", None)
    if config_path is not None and not json_output:
        info_log(f"{config_path.name} loaded", color)
    common.setup_dpi_awareness()
    handle = getattr(args, "handle", None)
    ref = getattr(args, "ref", None)
    if ref is not None:
        # ref は要素そのものを指す。座標を選ぶ手順を通らないので、
        # cursor_position は解決した要素の中心を参考情報として載せる。
        resolved = common._create_inspector(ref_backend(ref)).element_from_ref(ref)
        point = _element_point(resolved)
    else:
        point = _select_inspect_point(args, color, json_output, point_selector)
    if point is None:
        if not json_output:
            info_log("選択をキャンセルしました。", color)
        return 1
    cursor = CursorPosition(x=point[0], y=point[1])

    options = _selector_options_from_args(args)
    inspections: list[BackendInspection] = []
    for backend in _resolve_backends(args.backend, ref):
        inspector = common._create_inspector(backend)
        try:
            if ref is not None:
                log(f"{backend}: ref {ref} の要素を取得中です...")
                element = inspector.element_from_ref(ref)
            elif handle is None:
                log(f"{backend}: カーソル下の要素を取得中です...")
                element = inspector.element_from_point(cursor.x, cursor.y)
            else:
                log(f"{backend}: handle {handle:#x} の要素を取得中です...")
                element = inspector.element_from_handle(handle)
            inspections.append(_build_backend_inspection(backend, inspector, element, cursor, options, log))
        except StaleRefError:
            # 失効した ref は backend 単位の失敗ではなく、要求そのものの失敗として返す。
            raise
        except Exception as exc:
            inspections.append(BackendInspection(backend=backend, status="failed", message=str(exc)))

    result = InspectionResult(
        cursor_position=cursor,
        win32=_find_backend(inspections, "win32"),
        uia=_find_backend(inspections, "uia"),
    )
    output = (
        format_inspection_result_json(result)
        if json_output
        else format_inspection_result(result, args.detail, color, include_cursor=True)
    )
    print(output, end="")
    log_output = format_inspection_result_json(result) if json_output else format_inspection_result(result, args.detail, False, include_cursor=False)
    save_inspection_log(result, log_output, suffix=".json" if json_output else ".txt")
    return 0 if any(item.status == "success" for item in inspections) else 1


def _select_inspect_point(
    args: Namespace,
    color: bool,
    json_output: bool,
    point_selector: Callable[[], tuple[int, int] | None] | None,
) -> tuple[int, int] | None:
    if point_selector is not None:
        point = point_selector()
        if point is not None:
            time.sleep(OVERLAY_CLOSE_WAIT_SECONDS)
        return point

    at = getattr(args, "at", None)
    if at is not None:
        return at

    handle = getattr(args, "handle", None)
    if handle is not None:
        return _window_center(handle)

    delay = getattr(args, "delay", None)
    if delay is None:
        point = select_point_with_overlay()
        if point is not None:
            time.sleep(OVERLAY_CLOSE_WAIT_SECONDS)
        return point

    if json_output:
        time.sleep(delay)
    else:
        common.wait_with_countdown(delay, color)
    cursor = common.get_cursor_position()
    return (cursor.x, cursor.y)


def _window_center(handle: int) -> tuple[int, int]:
    """handle 指定時の cursor_position 用に、ウィンドウ矩形の中心を返す。

    要素自体は handle から解決するため、この座標は参考情報として出力する。
    """
    try:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(wintypes.HWND(handle), ctypes.byref(rect)):
            return (0, 0)
        return ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
    except Exception:
        return (0, 0)
