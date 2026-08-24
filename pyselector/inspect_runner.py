"""コマンド実行本体への入口。

実体は :mod:`pyselector.commands` 以下にある。このモジュールは import 経路を
保つための再エクスポートで、``run_*`` はすべてそちらに移した（設計 11 §12）。
"""

from __future__ import annotations

from pyselector.commands.act import run_act
from pyselector.commands.common import (
    DEFAULT_SELECTOR_EVALUATION_MAX_ITEMS,
    OVERLAY_CLOSE_WAIT_SECONDS,
    SelectorBuildOptions,
)
from pyselector.commands.diff import run_diff
from pyselector.commands.expect import evaluate_expectation, run_expect
from pyselector.commands.find import run_find, search_elements
from pyselector.commands.inspect import run_inspect
from pyselector.commands.tree import run_tree
from pyselector.commands.windows import run_windows

__all__ = [
    "DEFAULT_SELECTOR_EVALUATION_MAX_ITEMS",
    "OVERLAY_CLOSE_WAIT_SECONDS",
    "SelectorBuildOptions",
    "evaluate_expectation",
    "run_act",
    "run_diff",
    "run_expect",
    "run_find",
    "run_inspect",
    "run_tree",
    "run_windows",
    "search_elements",
]
