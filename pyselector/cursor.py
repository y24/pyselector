from __future__ import annotations

import ctypes
from ctypes import wintypes

from pyselector.model.inspection_result import CursorPosition
from pyselector.utils.errors import CursorError


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def get_cursor_position() -> CursorPosition:
    point = POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        raise CursorError("カーソル座標を取得できませんでした")
    return CursorPosition(x=point.x, y=point.y)
