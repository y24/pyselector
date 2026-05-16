from __future__ import annotations

from pathlib import Path


ROO_SKILL_RELATIVE_PATH = Path(".roo") / "skills" / "pyselector-cli" / "SKILL.md"

ROO_SKILL_CONTENT = """---
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

## Common Rules

- Run commands from the repository root unless the user specifies another working directory.
- Make sure the target Windows app is open before inspection.
- Use `inspect` when the user wants a selector for a specific visible element.
- Use `tree` when the user wants to explore a whole window or locate possible elements by title, class, control type, or automation id.
- Prefer `--backend win32` first for classic Windows apps.
- Use `--backend uia` for modern Windows apps, UWP/WinUI apps, or when win32 cannot see the target.
- Use `--backend both` when comparing candidates is useful.
- Keep `--scope window` for normal `inspect` runs.
- Use `--scope desktop` only when the candidate must be evaluated across multiple windows.
- Add `--include-hidden` only when hidden or offscreen elements are relevant.
- After execution, parse the JSON and use `selector_candidates`, `code_snippet`, `hierarchy`, and `element` fields to decide the most stable selector.

## Inspect A Clicked Element

Use this when the target element is visible and can be selected through the overlay.

```powershell
pyselector inspect --json --backend both
```

Useful variants:

```powershell
pyselector inspect --json --backend win32
pyselector inspect --json --backend uia
pyselector inspect --json --backend both --detail
pyselector inspect --json --backend both --scope desktop
pyselector inspect --json --backend uia --include-hidden
```

The command shows a full-desktop overlay. Left-click the target element to inspect it. Press Esc to cancel.

## Inspect A Window Tree

Use `tree` when you know the window title or need to discover descendant elements.

```powershell
pyselector tree --json --window-title "<window title>" --backend both
```

Useful variants:

```powershell
pyselector tree --json --window-title "<window title>" --backend uia --depth 5
pyselector tree --json --window-title "<title regex>" --title-re --backend uia
pyselector tree --json --window-title "<window title>" --backend both --max-items 100
pyselector tree --json --cursor --backend both --depth 3
pyselector tree --json --window-title "<window title>" --backend uia --include-hidden
```

`tree` requires exactly one of `--cursor` or `--window-title`.

## JSON Fields To Use

For `inspect`, read:

- `cursor_position`: clicked screen coordinate.
- `target_window`: top-level window metadata.
- `backends[].element`: element attributes such as `window_text`, `control_type`, `automation_id`, `class_name`, `rectangle`, and process info.
- `backends[].hierarchy`: parent chain from window/root to the target.
- `backends[].selector_candidates`: evaluated pywinauto candidates with hit counts and warnings.
- `backends[].code_snippet`: minimal pywinauto example for the best generated candidate.

For `tree`, read:

- `results[].root`: inspected tree root.
- `results[].nodes`: flattened hierarchy nodes with depth and attributes.
- `results[].reached_limit`: true when output was truncated by `--max-items`.

## Selector Choice Guidance

- Prefer candidates where `hits` is `1`.
- Prefer candidates using stable attributes such as `automation_id`, `control_type`, and meaningful `class_name`.
- Be careful with candidates that use window handles or `found_index`; these may change between app launches or UI changes.
- If all candidates have warnings or many hits, run `tree --json` and build a more specific parent-scoped selector from the hierarchy.
- When both backends work, choose the backend with the simpler stable selector and a reliable code snippet.

## Expected Workflow

1. Run an appropriate `pyselector ... --json` command.
2. Parse the JSON output.
3. Identify the best selector candidate and backend.
4. If the result is ambiguous, run a narrower `tree --json` command or repeat `inspect --json` with a different backend or visibility option.
"""


def install_roo_skill(base_dir: Path | None = None) -> Path:
    target = (base_dir or Path.cwd()) / ROO_SKILL_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(ROO_SKILL_CONTENT, encoding="utf-8", newline="\n")
    return target
