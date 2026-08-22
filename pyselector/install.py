from __future__ import annotations

from pathlib import Path


SKILL_RELATIVE_PATHS = {
    "copilot": Path(".github") / "skills" / "pyselector-cli" / "SKILL.md",
    "claude": Path(".claude") / "skills" / "pyselector-cli" / "SKILL.md",
}

SKILL_LABELS = {
    "copilot": "GitHub Copilot",
    "claude": "Claude Code",
}

SKILL_CONTENT = """---
name: pyselector-cli
description: Use the local pyselector CLI to inspect Windows UI elements and generate AI-readable pywinauto selector candidates in JSON.
---

# pyselector-cli Skill

Use this skill when a task needs Windows UI inspection, pywinauto selector discovery, UI tree exploration, or automation code that targets desktop application controls.

`pyselector` is a local CLI for inspecting Windows UI elements and generating pywinauto selector candidates.

Always include `--json` when running `pyselector`. The normal text output includes a startup logo and human-oriented sections that are unnecessary for an AI agent and harder to parse.

## When To Use

Use `pyselector` when the user asks to:

- Find a selector for a Windows button, input, menu item, list row, tab, dialog, or other UI element.
- Inspect a visible UI element in an open Windows application.
- Explore the UI tree of a known window.
- Generate or repair pywinauto automation code.
- Compare win32 and UIA backends for a target application.

Do not use it for web pages, browser DOM inspection, or non-Windows UI targets.

## Exploration Workflow

`inspect` without options opens a full-desktop overlay and waits for a human to click. **Never run it that way.** Use the non-interactive commands below instead.

Work from the outside in:

```powershell
# 1. Find the target window and its handle
pyselector windows --json

# 2. Grasp the size and shape of that window before dumping it
pyselector tree --json --window-handle 0x2E20F46 --summary

# 3. Narrow down to the elements you care about
pyselector find --json --window-handle 0x2E20F46 --control-type Button

# 4. Confirm the selector for the element you picked
pyselector find --json --window-handle 0x2E20F46 --text "Save" --with-selectors

# 5. Only if a single element still needs a full evaluation
pyselector inspect --json --at 636,2240
```

Each step narrows the search. Do not start from step 5, and do not dump a whole tree when `--summary` or `find` answers the question.

## Common Rules

- Run commands from the repository root unless the user specifies another working directory.
- Make sure the target Windows app is open before inspection.
- Prefer `--backend win32` first for classic Windows apps.
- Use `--backend uia` for modern Windows apps, UWP/WinUI apps, or when win32 cannot see the target.
- Use `--backend both` only when comparing candidates is actually useful; it doubles the work.
- Keep `--scope window` for normal `inspect` runs.
- Use `--scope desktop` only when the candidate must be evaluated across multiple windows.
- Add `--include-hidden` only when hidden or offscreen elements are relevant.
- After execution, parse the JSON and use `selector_candidates`, `code_snippet`, `hierarchy`, and `element` fields to decide the most stable selector.

## `windows`: Find The Target Window

```powershell
pyselector windows --json
pyselector windows --json --title "Calculator"
pyselector windows --json --process notepad.exe
pyselector windows --json --backend uia --include-hidden
```

Read `results[].windows[]`: `title`, `class_name`, `process_name`, `process_id`, `handle`, `rectangle`.

Use the `handle` value for every following command. It is more reliable than a title, which may match several windows.

## `find`: Search Elements By Condition

```powershell
pyselector find --json --window-handle 0x2E20F46 --control-type Button
pyselector find --json --window-handle 0x2E20F46 --text "Save" --with-selectors
pyselector find --json --window-handle 0x2E20F46 --auto-id num1Button --with-selectors
pyselector find --json --window-title "Notepad" --class-name Edit --backend win32
pyselector find --json --at 636,2240 --depth 2
```

`find` requires exactly one of `--window-handle`, `--window-title`, or `--at`.

Conditions are combined with AND: `--text` (case-insensitive substring), `--text-re`, `--auto-id`, `--control-type` (case-insensitive), `--class-name`, `--enabled-only`.

Read `results[].matches[]`:

- `point`: center of the element. Pass it straight to `inspect --at X,Y`.
- `handle`: present for win32 elements; often `null` for UIA.
- `depth`: distance from the search root.
- `element`: attributes of the element.
- `inspection`: present only with `--with-selectors`; same shape as an `inspect` backend entry.

Also read `scanned`, `total_matched`, `reached_limit` (the walk hit `--max-items`), and `truncated` (matches were cut by `--limit`). Widen `--depth` / `--max-items` when the element you expect is missing.

`--with-selectors` evaluates candidates only for the first `--selector-limit` matches (default 3), because evaluation is the expensive part. Narrow the conditions rather than raising that limit.

## `tree`: Explore A Window Structure

```powershell
pyselector tree --json --window-handle 0x2E20F46 --summary
pyselector tree --json --window-handle 0x2E20F46 --depth 3 --compact
pyselector tree --json --window-title "<window title>" --backend uia --depth 5
pyselector tree --json --window-title "<title regex>" --title-re --backend uia
```

`tree` requires exactly one of `--cursor`, `--window-title`, or `--window-handle`. Do not use `--cursor` as an agent: it waits on the mouse.

Start with `--summary`, which returns counts by `control_type` and `class_name` instead of every node. Use `--compact` to cut fields per node when you do need the nodes.

## `inspect --at` / `--handle`: Full Evaluation Of One Element

```powershell
pyselector inspect --json --at 636,2240
pyselector inspect --json --at 636,2240 --backend both
pyselector inspect --json --handle 0x2E20F46
```

`--at` takes a physical screen coordinate, the same coordinate space that `find` reports in `point` and `rectangle`.

`--handle` inspects the window itself, which is what you want for a top-level dialog. Inspecting its center coordinate would return a child control instead.

The screen may have changed since the coordinate was captured. Always check the returned `element.window_text` / `control_type` against what you expected before trusting the result.

## JSON Contract

Every `--json` response carries `schema_version`, `command`, and `status`.

`status` is `"success"` when at least one backend completed, even if nothing matched. A search that finds nothing returns `status: "success"` with an empty `matches` / `windows` array and exit code 1. A failure returns `status: "error"` with an `error` object holding `code`, `exit_code`, and `message`. Distinguish "not found" from "failed" by `status`, not by exit code alone.

For `inspect`, read:

- `cursor_position`: inspected screen coordinate.
- `target_window`: top-level window metadata.
- `backends[].element`: element attributes such as `window_text`, `control_type`, `automation_id`, `class_name`, `rectangle`, and process info.
- `backends[].hierarchy`: parent chain from window/root to the target.
- `backends[].selector_candidates`: evaluated pywinauto candidates with hit counts and warnings.
- `backends[].code_snippet`: minimal pywinauto example for the best generated candidate.

For `tree`, read:

- `results[].root`: inspected tree root.
- `results[].nodes`: flattened hierarchy nodes with depth and attributes.
- `results[].summary`: counts, present instead of `nodes` when `--summary` is used.
- `results[].reached_limit`: true when output was truncated by `--max-items`.

## Selector Choice Guidance

- Prefer candidates where `hits` is `1`.
- Prefer candidates using stable attributes such as `automation_id`, `control_type`, and meaningful `class_name`.
- Be careful with candidates that use window handles or `found_index`; these may change between app launches or UI changes.
- If all candidates have warnings or many hits, run `tree --json` and build a more specific parent-scoped selector from the hierarchy.
- When both backends work, choose the backend with the simpler stable selector and a reliable code snippet.

## Notes

- `pyselector` only reads the UI. It never clicks, types, or changes application state, so it cannot open a menu or switch a tab for you. Ask the user to bring the target screen into view first.
- Every invocation starts a new process, so handles and coordinates from a previous run are only valid while the screen is unchanged.
"""


def install_skill(kind: str, base_dir: Path | None = None) -> Path:
    try:
        relative_path = SKILL_RELATIVE_PATHS[kind]
    except KeyError:
        raise ValueError(f"unsupported skill kind: {kind}") from None
    target = (base_dir or Path.cwd()) / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(SKILL_CONTENT, encoding="utf-8", newline="\n")
    return target
