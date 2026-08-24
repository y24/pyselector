from __future__ import annotations

from argparse import Namespace

from pyselector.commands.common import _use_color
from pyselector.diff import diff_tree_payloads, load_tree_payload
from pyselector.output.json_output import format_diff_results_json
from pyselector.output.text_output import format_diff_result
from pyselector.utils.logging import info_log

def run_diff(args: Namespace) -> int:
    color = _use_color()
    json_output = getattr(args, "json", False)
    if not json_output:
        info_log("pyselector started", color)
    before = load_tree_payload(args.before)
    after = load_tree_payload(args.after)
    diffs = diff_tree_payloads(before, after)
    output = (
        format_diff_results_json(diffs, compact=getattr(args, "compact", False))
        if json_output
        else "".join(
            format_diff_result(diff, color, include_heading=index == 0)
            for index, diff in enumerate(diffs)
        )
    )
    print(output, end="")
    if not any(diff.status == "success" for diff in diffs):
        return 1
    return 0 if any(diff.has_differences for diff in diffs) else 1
