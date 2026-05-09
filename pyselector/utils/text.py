from __future__ import annotations

import json
import re


BLANK_MARKERS = {"(None)", "(Error)"}


def is_blank(value: str | None) -> bool:
    return value is None or value.strip() == "" or value in BLANK_MARKERS


def escape_python_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)[1:-1]


def escape_regex(value: str) -> str:
    return re.escape(value)
