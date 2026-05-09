from __future__ import annotations

from pyselector.model.rectangle import RectangleInfo


def format_value(value: object) -> str:
    if value is None:
        return "(None)"
    return str(value)


def format_handle(handle: int | None) -> str:
    if handle is None:
        return "(None)"
    return f"0x{handle:X}"


def format_rectangle(rectangle: RectangleInfo | None) -> str:
    if rectangle is None:
        return "(None)"
    return (
        f"L={rectangle.left}, T={rectangle.top}, R={rectangle.right}, B={rectangle.bottom}, "
        f"W={rectangle.width}, H={rectangle.height}"
    )


def quote_text(value: str | None) -> str:
    if value is None:
        return '"(None)"'
    return f'"{value}"'
