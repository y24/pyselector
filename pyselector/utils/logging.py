from __future__ import annotations

import sys


def verbose_log(enabled: bool, message: str) -> None:
    if enabled:
        print(f"[INFO] {message}", file=sys.stderr)
