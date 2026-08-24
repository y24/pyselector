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

SKILL_CONTENT = r"""---
name: pyselector-cli
description: Inspect Windows desktop UI elements, drive them, check their state, and generate pywinauto test code as JSON with the local pyselector CLI. Use when finding, verifying, or repairing a selector for a control in a Windows application (button, input, menu item, list row, tab, dialog), exploring a window's UI tree, comparing the win32 and UIA backends, writing or recording pywinauto automation and UI tests, launching a Windows app under test, asserting what is on screen, or screenshotting a window. Windows desktop apps only - not web pages or browser DOM.
---

# pyselector-cli

Local CLI that inspects Windows desktop UI elements, drives them, checks their state, and records a session as plain pywinauto test code. Windows desktop apps only.

**Always pass `--json`.** Text output carries human-oriented sections that only make parsing harder.

## Two things this tool is for

1. **Finding a selector** for a control, so you can write pywinauto code by hand.
2. **Writing a test end to end**: start the app, drive it, check the result, and emit a runnable pywinauto test.

Pick the second when the user asked for a test or for automation of a flow.

## Exploring: narrow from the outside in

```powershell
pyselector windows --json                                                 # 1. locate window -> handle
pyselector tree    --json --window-handle 0x2E20F46 --summary             # 2. size up that window
pyselector find    --json --window-handle 0x2E20F46 --control-type Button # 3. narrow to candidates
pyselector find    --json --window-handle 0x2E20F46 --text Save --with-selectors  # 4. confirm the selector
pyselector inspect --json --at 636,2240                                   # 5. only for a full one-element evaluation
```

Never start at step 5. Reuse the `handle` from step 1 in every later command; it is more reliable than a title, which can match several windows. To reach a screen that is not visible yet (a closed menu, another tab), see `act`.

**Never run bare `pyselector inspect` or `tree --cursor`** - both open an overlay and wait on a human mouse click.

## Recording a test end to end

```powershell
pyselector record start --name "check the calculation"

pyselector launch --json --app calculator --allow-actions                      # -> handle
pyselector act    --json --window-handle 0x2E20F46 --auto-id num5Button  --click --allow-actions
pyselector act    --json --window-handle 0x2E20F46 --auto-id plusButton  --click --allow-actions
pyselector act    --json --window-handle 0x2E20F46 --auto-id num3Button  --click --allow-actions
pyselector act    --json --window-handle 0x2E20F46 --auto-id equalButton --click --allow-actions
pyselector expect --json --window-handle 0x2E20F46 --auto-id CalculatorResults --value-contains "8" --wait 5

pyselector record stop --emit pytest --out tests/test_calc.py
```

Explore with `find` as much as you need in between; exploration is not recorded.

Before `stop`, run `record show --json` and check every step has a `selector`. Report anything with `selector: null` to the user instead of papering over it.

## Shared options

- `--backend win32` first for classic apps; `uia` for modern/UWP/WinUI apps or when win32 cannot see the target; `both` only when comparing candidates is genuinely useful (it doubles the work). `act`, `expect`, `shot`, `launch` and `close` take one backend only, never `both`.
- `--scope window` normally; `--scope desktop` only to evaluate a candidate across multiple windows.
- `--include-hidden` only when hidden or offscreen elements are relevant.
- Run from the repository root unless the user says otherwise. The target app must already be open, unless you open it with `launch`.
- Only `act`, `launch` and `close` change the desktop, and only through both gates below. `shot --out` and `record stop --out` write files, and neither overwrites an existing one without `--force`. Everything else only reads.
- Handles and coordinates captured earlier hold only while the screen is unchanged; a `ref` additionally dies with its server.

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
pyselector find --json --window-handle 0x2E20F46 --auto-id dialog --wait 5
```

Requires exactly one of `--window-handle` / `--window-title` / `--at` / `--ref`. Conditions AND together: `--text` (case-insensitive substring), `--text-re`, `--auto-id`, `--control-type` (case-insensitive), `--class-name`, `--enabled-only`.

`results[].matches[]`: `point` (element center; feed straight to `inspect --at`), `handle` (win32 only, often `null` on UIA), `depth`, `element`, and `inspection` (only with `--with-selectors`; same shape as an `inspect` backend entry). Also read `scanned`, `total_matched`, `reached_limit` (the walk hit `--max-items`) and `truncated` (matches cut by `--limit`); widen `--depth` / `--max-items` when an expected element is missing.

`--with-selectors` evaluates candidates only for the first `--selector-limit` matches (default 3), since evaluation is the expensive part. Narrow the conditions rather than raising that limit.

`--with-state` additionally reads `value` / `is_checked` / `is_selected` for the listed matches. `--wait` / `--wait-gone` are described under **Waiting**.

## `tree`: explore a window structure

```powershell
pyselector tree --json --window-handle 0x2E20F46 --summary
pyselector tree --json --window-handle 0x2E20F46 --depth 3 --compact
pyselector tree --json --window-title "<title regex>" --title-re --backend uia
```

Requires exactly one of `--window-handle` / `--window-title` / `--ref` / `--cursor` (never `--cursor`). Start with `--summary`, which returns counts by `control_type` and `class_name` instead of every node; add `--compact` to trim fields when you do need nodes. Never dump a whole tree when `--summary` or `find` answers the question.

`results[]`: `root`, `nodes` (flattened hierarchy with depth and attributes), `summary` (replaces `nodes` under `--summary`), `reached_limit`.

## `inspect`: full evaluation of one element

```powershell
pyselector inspect --json --at 636,2240 [--backend both]
pyselector inspect --json --handle 0x2E20F46
```

`--at` takes a physical screen coordinate, the same space `find` reports in `point` and `rectangle`. Use `--handle` for a top-level window or dialog itself; inspecting its center coordinate would return a child control. The screen may have changed since a coordinate was captured, so check the returned `element.window_text` / `control_type` against what you expected.

Response: `cursor_position`, `target_window`, and `backends[]` with `element` (attributes and `state`), `hierarchy` (parent chain to the target), `selector_candidates` (evaluated pywinauto candidates with hit counts and warnings), `code_snippet`.

## `act`: drive the UI

`act` changes application state (as do `launch` and `close`), so it is gated twice: the working directory needs `PYSELECTOR_ALLOW_ACTIONS=true` in its `.env`, **and** each command must pass `--allow-actions`. Either gate missing fails with `action_not_allowed` (exit 7) and nothing happens. Always resolve the target with `--dry-run` first: it skips both gates and reports exactly which element would be acted on.

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

`--settle SEC` waits after the action until the window stops changing, at most SEC seconds. It is not a fixed sleep: a still screen returns at once. Use it when a click starts an animation or loads content, and it pairs with `--diff` (the settled tree becomes the "after" snapshot).

Rules: prefer `--invoke` over `--click` where it works (UIA invoke pattern, no physical mouse). Re-read state between actions instead of assuming it. Never act on a target you have not resolved with `--dry-run` or `find`. Never dismiss dialogs, confirm prompts, delete data, submit forms, or send anything unless the user asked for that specific step.

**Report the outcome of each `act` before moving on.** State the exit code and `status`, and say what the element looks like afterwards (`element_after`, or `diff` when you asked for it). Do not chain a second action on the assumption that the first worked.

An action can also fail because pywinauto has no matching method for that control: `action_failed` (exit 8) lists what was tried, for example `set_edit_text: unsupported`. That is a limit of the control, not a wrong selector - use `--focus` followed by `--send-keys` rather than retrying the same way.

`action_not_allowed` (exit 7) has three causes and `error.message` names which one:

- **`.env` not set** - the directory you run from has no `PYSELECTOR_ALLOW_ACTIONS=true` in `.env`. That file is deliberately uncommitted, so a fresh clone always starts here. **Do not create or edit `.env` yourself**, that would be granting yourself control of the desktop: ask the user to add the line. Meanwhile use `--dry-run` to have the exact `act` command ready for when they do.
- **flag missing** - you left off `--allow-actions`. Retry with it.
- **resident server** - both gates are fine, but the running server was started without action permission. Report that rather than starting or stopping servers yourself.

## `expect`: check a condition

**Never decide that a check passed by reading a tree dump yourself.** A dump is a snapshot of a moment that has already gone by, and reading one is exactly where a wrong conclusion goes unnoticed. Express the check as an `expect` command so the tool re-reads the live UI and reports the verdict.

Targeting is identical to `find`, and ambiguity fails the same way as in `act` (exit 6). Exactly one expectation per command:

```powershell
pyselector expect --json --window-handle 0x2E20F46 --auto-id saveBtn --exists
pyselector expect --json --window-handle 0x2E20F46 --auto-id dialog --not-exists
pyselector expect --json --window-handle 0x2E20F46 --control-type Button --count 5
pyselector expect --json --window-handle 0x2E20F46 --auto-id nameBox --value-contains "Yam"
pyselector expect --json --window-handle 0x2E20F46 --auto-id agree --checked
```

| Expectation | Needs the target to be unique |
| --- | --- |
| `--exists` / `--not-exists` / `--count N` | no |
| `--value-equals` / `--value-contains` | yes |
| `--checked` / `--unchecked` | yes |
| `--enabled` / `--disabled` | yes |

**"The check did not hold" and "the check could not run" are different results.** `satisfied: false` with `status: "success"` (exit 12) means the UI is not in the expected state. `status: "error"` means the search itself failed - a missing window, a bad handle. Read `satisfied`, not the exit code alone. `expectation.actual` carries what was actually found, and `matched` tells you whether anything was there at all.

`--value-*` and `--checked` read live UIA state. `--backend win32` cannot report `value`, because in win32 a value is indistinguishable from the label text - use `uia` for those.

## Waiting

The UI does not finish drawing the moment an action returns. Rather than sleeping, ask for the state you expect:

```powershell
pyselector find   --json --window-handle 0x2E20F46 --auto-id dialog --wait 5
pyselector find   --json --window-handle 0x2E20F46 --auto-id spinner --wait-gone 5
pyselector expect --json --window-handle 0x2E20F46 --auto-id result --value-contains "done" --wait 10
pyselector act    --json --ref uia:7f3a2b:42 --click --allow-actions --settle 3
```

A timeout is not an error: you get the last attempt's result, so `find --wait` ends with zero matches and `expect --wait` with `satisfied: false`. The response reports `waited`, `attempts` and `timed_out`.

When you are recording, reach for `expect --wait` rather than `act --settle`: a waited expectation becomes a `wait(...)` line in the generated test, while `--settle` is a pyselector-only idea and generates nothing.

## `shot`: see the screen

Element trees cannot express custom-drawn controls, icon-only buttons or rendering problems. Take a picture when the tree is not telling you enough.

```powershell
pyselector shot --json --window-handle 0x2E20F46 --out shot.png
pyselector shot --json --ref uia:7f3a2b:42 --out button.png
pyselector shot --json --screen --out desktop.png
pyselector shot --json --window-handle 0x2E20F46 --annotate --control-type Button --out buttons.png
```

`--annotate` takes the same conditions as `find` and draws a numbered box over every match, returning the number-to-element mapping in `annotations`. Use it to settle "which one of these is the Save button" by looking at the picture. It needs a window; it cannot be combined with `--screen`.

`origin` is the screen coordinate of the image's top-left corner, so you can line an element `rectangle` up with what you see.

## `launch` / `close`: put the app in a known state

Both pass the same two gates as `act` and both support `--dry-run`.

```powershell
pyselector launch --json --exe "C:\Windows\System32\calc.exe" --wait-title-re "Calculator" --allow-actions
pyselector launch --json --app calculator --allow-actions
pyselector close  --json --window-handle 0x2E20F46 --allow-actions
```

`launch` returns the `pid` and the main window's `handle` - **feed that handle straight into every later command**. `--app NAME` reads an entry from the `apps` section of `pyselector_config.json` (`exe`, `args`, `window_title_re`, `timeout`); ask the user to add one rather than hard-coding a path if they will run this repeatedly. `--attach-existing` connects to a matching window instead of opening a second instance.

Prefer `--wait-title-re` over relying on the process id: apps like `calc.exe` hand their window to a different process. When an instance is already open, `launch` prefers a window that appeared after it started - but a tabbed app that reuses its existing window will hand you that one, so check the `title` you got back is the screen you meant.

`close` asks the window to close. `--force` ends the process instead, which can destroy unsaved work - only use it when the user asked for it.

## `record`: turn the session into a test

Recording makes every successful `act` and every satisfied `expect` accumulate into a runnable pywinauto test. **The generated file does not import pyselector.**

```powershell
pyselector record start --name "save flow"
# ... launch / act / expect as usual ...
pyselector record show --json
pyselector record stop --emit pytest --out tests/test_save_flow.py
```

- `start --name` names the test function, so give it something descriptive.
- `--emit pytest` (default) writes a test with a `window` fixture; `--emit plain` writes a standalone script; `--emit none` returns the raw recording.
- Without `--out` the code comes back in the response; with `--out` it is written to that path.
- `record cancel` throws the recording away. `record status` says whether one is running.
- Only one recording exists at a time, per user. `start` refuses to replace one without `--force`.
- `--note "..."` on `act` and `expect` adds a comment to that step in the generated code.

| Recorded | Not recorded |
| --- | --- |
| `act` that actually ran | `act --dry-run` |
| `expect` that was satisfied | `expect` that failed |
| `launch`, `close` | `find`, `tree`, `inspect`, `shot` |

A failed expectation is left out because writing it down would produce an assertion guaranteed to fail.

While recording, `act` and `expect` also evaluate selector candidates for the resolved element and store the best one, so what lands in the code is a stable selector rather than the conditions you happened to type. That costs an extra evaluation per step, only while recording. If `recorded.selector` is `null`, the generated code will contain a `NotImplementedError` for you to fill in, and the honest move is to tell the user rather than to invent a selector.

## `batch`: several commands in one call

```powershell
pyselector batch --json steps.json
```

```json
{
  "steps": [
    { "command": "act",    "args": ["--ref", "uia:7f3a2b:42", "--click", "--allow-actions"] },
    { "command": "expect", "args": ["--window-handle", "0x2E20F46", "--auto-id", "dialog", "--exists", "--wait", "5"] }
  ]
}
```

Every step runs with `--json`, and each envelope comes back in `steps[].result` with its own `exit_code`. The run stops at the first failure and returns that exit code (`--continue-on-error` runs them all). `batch`, `serve` and `install-skills` cannot be steps.

Use it when every argument is already known - replaying a sequence you have confirmed. There is no variable substitution between steps: if step 2 depends on what step 1 returned, run them separately and read the result yourself.

## `diff`: compare two snapshots

```powershell
pyselector tree --json --window-handle 0x2E20F46 --depth 8 > before.json
# ... something changes the screen ...
pyselector tree --json --window-handle 0x2E20F46 --depth 8 > after.json
pyselector diff --json before.json after.json
```

`results[]`: `added`, `removed`, `changed` (`before` / `after` per field), `summary`. Exit 0 means differences were found, 1 means identical. Snapshots taken with `--summary` cannot be compared. Use `act --diff` when you are the one causing the change.

## When `find` or `expect` turns up nothing

Zero matches is a result, not a failure: `status` stays `"success"` and `matches` is empty. Work down this list in order rather than inventing new conditions:

1. Raise `--depth` / `--max-items`, and check `reached_limit` - the walk may have been cut short.
2. Drop one condition. `--control-type` is the usual culprit; UIA and win32 name types differently.
3. Loosen `--text` to `--text-re`. `--text` is already a case-insensitive substring, so if it fails the text itself is different.
4. Switch `--backend` (win32 <-> uia). A control invisible to one is often plain in the other.
5. Add `--include-hidden` when the element may be scrolled out or collapsed.
6. Run `tree --json --summary` and re-read the structure instead of guessing.
7. Consider that the element is not on screen yet: open the menu or tab with `act --diff`, then search inside `diff.added`.
8. Add `--wait 5` when the screen may still be drawing.
9. Take a `shot` and look at it.

Stop and report to the user once you have worked through this without success. Do not keep trying variations on a screen you have not understood - on a tool that drives the real desktop, that is how the wrong thing gets clicked.

## Element refs (resident mode)

A resident server may be running for this repository. It starts on demand, stops when idle, and changes nothing about how you invoke commands. When the envelope reports `"served": true`, elements carry a `ref`:

```powershell
pyselector find --json --window-handle 0x2E20F46 --auto-id saveBtn   # -> "ref": "uia:7f3a2b:42"
pyselector act  --json --ref uia:7f3a2b:42 --click --allow-actions
```

A `ref` names one exact element, so prefer it over re-running `find` or reusing a coordinate. It works with `inspect`, `tree`, `find`, `act`, `expect` and `shot`, and replaces `--at` / `--window-handle` / `--window-title`.

- A `ref` is valid only while the server that issued it runs. It never appears when `served` is `false`, and you must not invent one.
- If the screen changed or the server restarted, the command fails with `stale_ref` (exit 9) and **performs no action**; run `find` again for a fresh `ref`.
- Pass `--server require` when you need refs: otherwise a command may silently fall back to local execution and return none. It fails with `server_unavailable` (exit 11) when no server is reachable.
- `launch`, `close`, `shot`, `record` and `batch` never go through the server, so they never mint refs.

## JSON contract

Every `--json` response carries `schema_version`, `command`, `status`, `served`. `schema_version` only ever gains keys, so read the fields you need rather than comparing versions. `served` is `false` for ordinary one-shot execution.

`status` is `"success"` when at least one backend completed, even if nothing matched. A failure returns `"error"` with an `error` object holding `code`, `exit_code`, `message`. **Distinguish "not found" from "failed" by `status`, not by exit code alone.**

Exit codes worth recognising: `1` nothing matched, `6` `ambiguous_target`, `7` `action_not_allowed`, `8` `action_failed`, `9` `stale_ref`, `10` argument error, `11` `server_unavailable`, `12` expectation not satisfied, `13` screenshot failed.

Elements carry a `state` object (`value`, `is_checked`, `is_selected`, `is_offscreen`, `has_keyboard_focus`) only where it was actually read: always in `inspect` and `act`, in `expect` when the check needs it, and in `find` under `--with-state`. Reading state costs a UIA call per element, so `find` leaves it off by default. A `null` inside `state` means the control does not expose that property - notably `is_checked` is `null` for a tri-state checkbox that is neither on nor off, and neither `--checked` nor `--unchecked` will be satisfied by it.

## Choosing a selector

- Prefer candidates with `hits: 1` and stable attributes such as `automation_id`, `control_type`, and a meaningful `class_name`.
- Distrust candidates built on window handles or `found_index`; they shift between app launches and UI changes.
- If every candidate has warnings or many hits, run `tree` and build a more specific parent-scoped selector from the hierarchy.
- When both backends work, take the one with the simpler stable selector and a reliable code snippet.
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
