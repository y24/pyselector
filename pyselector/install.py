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
description: Inspect Windows desktop UI elements and generate pywinauto selector candidates as JSON with the local pyselector CLI. Use when finding, verifying, or repairing a selector for a control in a Windows application (button, input, menu item, list row, tab, dialog), exploring a window's UI tree, comparing the win32 and UIA backends, or writing pywinauto automation code. Windows desktop apps only - not web pages or browser DOM.
---

# pyselector-cli

Local CLI that inspects Windows desktop UI elements and generates pywinauto selector candidates. Windows desktop apps only.

**Always pass `--json`.** Text output carries a human-oriented sections that only make parsing harder.

## Workflow: narrow from the outside in

```powershell
pyselector windows --json                                                 # 1. locate window -> handle
pyselector tree    --json --window-handle 0x2E20F46 --summary             # 2. size up that window
pyselector find    --json --window-handle 0x2E20F46 --control-type Button # 3. narrow to candidates
pyselector find    --json --window-handle 0x2E20F46 --text Save --with-selectors  # 4. confirm the selector
pyselector inspect --json --at 636,2240                                   # 5. only for a full one-element evaluation
```

Never start at step 5, and never dump a whole tree when `--summary` or `find` answers the question.

**Never run bare `pyselector inspect` or `tree --cursor`** - both open an overlay and wait on a human mouse click.

Reuse the `handle` from step 1 in every later command; it is more reliable than a title, which can match several windows. To reach a screen that is not visible yet (a closed menu, another tab), see `act`.

## Shared options

- `--backend win32` first for classic apps; `uia` for modern/UWP/WinUI apps or when win32 cannot see the target; `both` only when comparing candidates is genuinely useful (it doubles the work).
- `--scope window` normally; `--scope desktop` only to evaluate a candidate across multiple windows.
- `--include-hidden` only when hidden or offscreen elements are relevant.
- Run from the repository root unless the user says otherwise, and make sure the target app is open.

## `windows`: find the target window

```powershell
pyselector windows --json [--title Calculator] [--process notepad.exe] [--backend uia] [--include-hidden]
```

`results[].windows[]`: `title`, `class_name`, `process_name`, `process_id`, `handle`, `rectangle`.

## `find`: search elements by condition

```powershell
pyselector find --json --window-handle 0x2E20F46 --control-type Button
pyselector find --json --window-handle 0x2E20F46 --text Save --with-selectors
pyselector find --json --window-title Notepad --class-name Edit --backend win32
pyselector find --json --at 636,2240 --depth 2
```

Requires exactly one of `--window-handle` / `--window-title` / `--at`. Conditions AND together: `--text` (case-insensitive substring), `--text-re`, `--auto-id`, `--control-type` (case-insensitive), `--class-name`, `--enabled-only`.

`results[].matches[]`: `point` (element center; feed straight to `inspect --at`), `handle` (win32 only, often `null` on UIA), `depth`, `element`, and `inspection` (only with `--with-selectors`; same shape as an `inspect` backend entry). Also read `scanned`, `total_matched`, `reached_limit` (the walk hit `--max-items`) and `truncated` (matches cut by `--limit`); widen `--depth` / `--max-items` when an expected element is missing.

`--with-selectors` evaluates candidates only for the first `--selector-limit` matches (default 3), since evaluation is the expensive part. Narrow the conditions rather than raising that limit.

## `tree`: explore a window structure

```powershell
pyselector tree --json --window-handle 0x2E20F46 --summary
pyselector tree --json --window-handle 0x2E20F46 --depth 3 --compact
pyselector tree --json --window-title "<title regex>" --title-re --backend uia
```

Requires exactly one of `--window-handle` / `--window-title` / `--cursor` (never `--cursor`). Start with `--summary`, which returns counts by `control_type` and `class_name` instead of every node; add `--compact` to trim fields when you do need nodes.

`results[]`: `root`, `nodes` (flattened hierarchy with depth and attributes), `summary` (replaces `nodes` under `--summary`), `reached_limit`.

## `inspect`: full evaluation of one element

```powershell
pyselector inspect --json --at 636,2240 [--backend both]
pyselector inspect --json --handle 0x2E20F46
```

`--at` takes a physical screen coordinate, the same space `find` reports in `point` and `rectangle`. Use `--handle` for a top-level window or dialog itself; inspecting its center coordinate would return a child control. The screen may have changed since a coordinate was captured, so check the returned `element.window_text` / `control_type` against what you expected.

Response: `cursor_position`, `target_window`, and `backends[]` with `element` (attributes), `hierarchy` (parent chain to the target), `selector_candidates` (evaluated pywinauto candidates with hit counts and warnings), `code_snippet`.

## `act`: drive the UI

`act` is the only command that changes application state, so it is gated twice: the working directory needs `PYSELECTOR_ALLOW_ACTIONS=true` in its `.env`, **and** each command must pass `--allow-actions`. Either gate missing fails with `action_not_allowed` (exit 7) and nothing happens. Always resolve the target with `--dry-run` first: it skips both gates and reports exactly which element would be acted on.

```powershell
pyselector act --json --window-handle 0x2E20F46 --auto-id num5Button --click --dry-run
pyselector act --json --window-handle 0x2E20F46 --auto-id num5Button --click --allow-actions
pyselector act --json --window-handle 0x2E20F46 --auto-id searchBox --set-text "query" --allow-actions
pyselector act --json --window-handle 0x2E20F46 --auto-id searchBox --send-keys "{ENTER}" --allow-actions
pyselector act --json --window-handle 0x2E20F46 --auto-id TogglePaneButton --click --allow-actions --diff
```

Exactly one action per command: `--click`, `--double-click`, `--right-click`, `--invoke`, `--focus`, `--set-text TEXT`, `--send-keys KEYS`.

Targeting uses the same conditions as `find` and **must be unique**: several matches means `ambiguous_target` (exit 6) with the candidates listed, so narrow the conditions or pass `--index N`. `--at X,Y` names the target directly and cannot be combined with conditions.

`--diff` reports what the action changed in that window. This is how you reach a screen that is not visible yet: open a menu or switch a tab, read `diff.added`, then `find` inside the new elements.

Rules: prefer `--invoke` over `--click` where it works (UIA invoke pattern, no physical mouse). Re-read state between actions instead of assuming it. Never act on a target you have not resolved with `--dry-run` or `find`. Never dismiss dialogs, confirm prompts, delete data, submit forms, or send anything unless the user asked for that specific step.

### When `act` is refused

`action_not_allowed` (exit 7) has three causes and `error.message` names which one:

- **`.env` not set** - the directory you run from has no `PYSELECTOR_ALLOW_ACTIONS=true` in `.env`. That file is deliberately uncommitted, so a fresh clone always starts here. **Do not create or edit `.env` yourself**, that would be granting yourself control of the desktop: ask the user to add the line `PYSELECTOR_ALLOW_ACTIONS=true` to `.env` in the working directory. Every other command keeps working meanwhile, so use `--dry-run` to have the exact `act` command ready for when they do.
- **flag missing** - you left off `--allow-actions`. Retry with it.
- **resident server** - `.env` and the flag are both fine, but the running server was started without action permission. Report that to the user rather than starting or stopping servers yourself.

## `diff`: compare two snapshots

```powershell
pyselector tree --json --window-handle 0x2E20F46 --depth 8 > before.json
# ... something changes the screen ...
pyselector tree --json --window-handle 0x2E20F46 --depth 8 > after.json
pyselector diff --json before.json after.json
```

`results[]`: `added`, `removed`, `changed` (`before` / `after` per field), `summary`. Exit 0 means differences were found, 1 means identical. Snapshots taken with `--summary` cannot be compared. Use `act --diff` when you are the one causing the change.

## Element refs (resident mode)

A resident server may be running for this repository. It starts on demand, stops when idle, and changes nothing about how you invoke commands. When the envelope reports `"served": true`, elements carry a `ref`:

```powershell
pyselector find --json --window-handle 0x2E20F46 --auto-id saveBtn   # -> "ref": "uia:7f3a2b:42"
pyselector act  --json --ref uia:7f3a2b:42 --click --allow-actions
```

A `ref` names one exact element, so prefer it over re-running `find` or reusing a coordinate. It works with `inspect`, `tree`, `find` and `act`, and replaces `--at` / `--window-handle` / `--window-title`.

- A `ref` is valid only while the server that issued it runs. It never appears when `served` is `false`, and you must not invent one.
- If the screen changed or the server restarted, the command fails with `stale_ref` (exit 9) and **performs no action**; run `find` again for a fresh `ref`.
- Pass `--server require` when you need refs: otherwise a command may silently fall back to local execution and return none. It fails with `server_unavailable` (exit 11) when no server is reachable.

## JSON contract

Every `--json` response carries `schema_version`, `command`, `status`, `served`. `schema_version` only ever gains keys, so read the fields you need rather than comparing versions. `served` is `false` for ordinary one-shot execution.

`status` is `"success"` when at least one backend completed, even if nothing matched: a search that finds nothing returns `"success"` with an empty `matches` / `windows` array and exit code 1. A failure returns `"error"` with an `error` object holding `code`, `exit_code`, `message`. **Distinguish "not found" from "failed" by `status`, not by exit code alone.**

## Choosing a selector

- Prefer candidates with `hits: 1` and stable attributes such as `automation_id`, `control_type`, and a meaningful `class_name`.
- Distrust candidates built on window handles or `found_index`; they shift between app launches and UI changes.
- If every candidate has warnings or many hits, run `tree` and build a more specific parent-scoped selector from the hierarchy.
- When both backends work, take the one with the simpler stable selector and a reliable code snippet.
- Every command except `act` only reads the UI. Handles and coordinates from an earlier run hold only while the screen is unchanged; a `ref` additionally dies with its server.
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
