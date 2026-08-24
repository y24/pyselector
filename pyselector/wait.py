from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

#: ポーリング間隔の既定値（秒）。UI の走査そのものに 1 秒近くかかるため、
#: これより詰めても試行回数が増えるだけで、結果が早く得られるわけではない。
DEFAULT_POLL_INTERVAL = 0.3

T = TypeVar("T")


@dataclass(frozen=True)
class WaitOutcome:
    """待った結果。1 回で決まったのか粘ったのかを出力に残すために使う。"""

    waited: float
    attempts: int
    timed_out: bool

    @property
    def rounded(self) -> float:
        return round(self.waited, 3)


def poll_until(
    attempt: Callable[[], T],
    is_done: Callable[[T], bool],
    timeout: float | None,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[T, WaitOutcome]:
    """条件が満たされるまで ``attempt`` を繰り返し、最後の結果を返す。

    タイムアウトは失敗ではない。最後の試行の結果をそのまま返し、判断は
    呼び出し側に委ねる。find なら 0 件、expect なら satisfied=false として
    現れるので、「待ったが駄目だった」ことは結果そのものから読める。

    ``timeout`` が None または 0 のときも 1 回は必ず実行する。待機を指定しない
    ことと、待機を指定して即座に成立することは、結果として同じであるべき。
    """
    started = now()
    attempts = 0
    while True:
        result = attempt()
        attempts += 1
        elapsed = now() - started
        if is_done(result):
            return result, WaitOutcome(waited=elapsed, attempts=attempts, timed_out=False)
        if not timeout or elapsed >= timeout:
            return result, WaitOutcome(waited=elapsed, attempts=attempts, timed_out=bool(timeout))
        sleep(min(poll_interval, max(timeout - elapsed, 0.0)))


def poll_until_stable(
    snapshot: Callable[[], T],
    timeout: float,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[T, WaitOutcome]:
    """連続する 2 回の観測が一致するまで待ち、最後の観測を返す。

    固定の sleep ではないため、変化の無い画面では 2 回目の観測で即座に返る。
    """
    started = now()
    previous = snapshot()
    attempts = 1
    while True:
        elapsed = now() - started
        if elapsed >= timeout:
            return previous, WaitOutcome(waited=elapsed, attempts=attempts, timed_out=True)
        sleep(min(poll_interval, max(timeout - elapsed, 0.0)))
        current = snapshot()
        attempts += 1
        if current == previous:
            return current, WaitOutcome(waited=now() - started, attempts=attempts, timed_out=False)
        previous = current
