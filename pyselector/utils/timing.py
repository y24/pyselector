from __future__ import annotations

import time
from contextlib import contextmanager
from collections.abc import Iterator


@contextmanager
def elapsed_timer() -> Iterator[callable]:
    start = time.monotonic()
    yield lambda: time.monotonic() - start
