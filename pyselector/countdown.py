from __future__ import annotations

import time

from pyselector.utils.logging import info_log


def wait_with_countdown(delay: int, color: bool = False) -> None:
    if delay <= 0:
        return
    info_log(f"{delay}秒後にカーソル下のUI要素を取得します", color)
    for remaining in range(delay, 0, -1):
        info_log(f"{remaining}...", color)
        time.sleep(1)
