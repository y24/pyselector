from __future__ import annotations

import sys

RESET = "\033[0m"
GRAY = "\033[90m"


def format_info(message: str, color: bool = False) -> str:
    line = f"[INFO] {message}"
    if not color:
        return line
    return f"{GRAY}{line}{RESET}"


def info_log(message: str, color: bool = False) -> None:
    print(format_info(message, color), flush=True)


def verbose_log(enabled: bool, message: str) -> None:
    if enabled:
        print(format_info(message), file=sys.stderr, flush=True)
