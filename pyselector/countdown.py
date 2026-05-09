from __future__ import annotations

import time


def wait_with_countdown(delay: int) -> None:
    if delay <= 0:
        return
    print(f"[INFO] {delay}秒後にカーソル下のUI要素を取得します")
    for remaining in range(delay, 0, -1):
        print(f"[INFO] {remaining}...")
        time.sleep(1)
