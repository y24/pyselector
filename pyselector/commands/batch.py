from __future__ import annotations

import contextlib
import io
import json
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

from pyselector.commands.common import _use_color
from pyselector.model.batch_result import BatchResult, BatchStepResult
from pyselector.output.json_output import format_batch_result_json
from pyselector.output.text_output import format_batch_result
from pyselector.utils.errors import ArgumentError
from pyselector.utils.logging import info_log

#: ステップに指定できないコマンド。batch は再帰するため、serve と install-skills は
#: 一括実行の中に混ぜる意味が無く、対話的な処理を持ち込む恐れがある。
FORBIDDEN_STEP_COMMANDS = frozenset({"batch", "serve", "install-skills"})

STDIN_MARKER = "-"


def run_batch(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    if not json_output:
        info_log("pyselector started", color)

    steps = _load_steps(args.steps)
    continue_on_error = getattr(args, "continue_on_error", False)

    results: list[BatchStepResult] = []
    failed_code = 0
    for index, step in enumerate(steps):
        argv = _argv(step, index)
        if not json_output:
            info_log(f"[{index + 1}/{len(steps)}] {' '.join(argv)}", color)
        exit_code, payload, raw = _execute(argv)
        results.append(BatchStepResult(index=index, argv=argv, exit_code=exit_code, result=payload, output=raw))
        if exit_code != 0:
            failed_code = failed_code or exit_code
            if not continue_on_error:
                break

    result = BatchResult(steps=results, requested=len(steps), failed_exit_code=failed_code)
    output = format_batch_result_json(result) if json_output else format_batch_result(result, color)
    print(output, end="")
    return failed_code


def _load_steps(source: str) -> list[dict[str, Any]]:
    if source == STDIN_MARKER:
        text = sys.stdin.read()
        origin = "standard input"
    else:
        path = Path(source)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ArgumentError(f"ステップを読めません: {path}: {exc}") from exc
        origin = str(path)

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ArgumentError(f"ステップの JSON を解釈できません: {origin}: {exc}") from exc

    steps = raw.get("steps") if isinstance(raw, dict) else raw
    if not isinstance(steps, list) or not steps:
        raise ArgumentError(f"steps に 1 件以上の配列が必要です: {origin}")
    return steps


def _argv(step: Any, index: int) -> list[str]:
    if not isinstance(step, dict):
        raise ArgumentError(f"ステップはオブジェクトである必要があります: steps[{index}]")
    command = step.get("command")
    if not isinstance(command, str) or not command:
        raise ArgumentError(f"command が必要です: steps[{index}]")
    if command in FORBIDDEN_STEP_COMMANDS:
        raise ArgumentError(f"batch のステップに指定できないコマンドです: {command}: steps[{index}]")
    step_args = step.get("args", [])
    if not isinstance(step_args, list) or any(not isinstance(item, str) for item in step_args):
        raise ArgumentError(f"args は文字列の配列である必要があります: steps[{index}]")
    argv = [command, *step_args]
    # ステップの結果を機械的に読めるようにするため、必ず JSON で実行する。
    if "--json" not in argv:
        argv.append("--json")
    return argv


def _execute(argv: list[str]) -> tuple[int, dict[str, Any] | None, str | None]:
    """1 ステップを、同じプロセスの main() として実行する。

    プロセスを起こし直さないので、1 コマンドあたりの固定コストが消える。ただし
    要素参照はローカル実行では 1 コマンドで失効するという性質のままなので、ステップ間で
    ref を持ち回れるのは常駐サーバー経由のときだけである。
    """
    from pyselector.cli import main

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exit_code = main(list(argv))
    text = buffer.getvalue()
    try:
        return exit_code, json.loads(text), None
    except json.JSONDecodeError:
        # JSON にならなかった出力も捨てずに返す。原因の手がかりになる。
        return exit_code, None, text
