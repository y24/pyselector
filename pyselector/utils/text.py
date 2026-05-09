from __future__ import annotations

import re


BLANK_MARKERS = {"(None)", "(Error)"}


def is_blank(value: str | None) -> bool:
    return value is None or value.strip() == "" or value in BLANK_MARKERS


def escape_python_string(value: str) -> str:
    return value.encode("unicode_escape").decode("ascii").replace('"', '\\"')


def escape_regex(value: str) -> str:
    return re.escape(value)
