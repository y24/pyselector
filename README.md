# pyselector

pyselector is a CLI tool for inspecting Windows UI elements and generating pywinauto selector candidates.

It is intended for QA engineers, test automation developers, and RPA script authors who need to identify desktop UI elements for pywinauto automation.

## Install

```bash
pip install .
```

For development:

```bash
pip install -e .
```

## Commands

```bash
pyselector --help
pyselector version
pyselector inspect
pyselector inspect --delay 0
pyselector inspect --backend win32
pyselector inspect --backend uia
pyselector tree --cursor
pyselector tree --window-title "電卓"
```

When no subcommand is supplied, `inspect` is used.

## Inspect

`inspect` waits for the configured delay, reads the current cursor position, then tries to inspect the UI element under the cursor with Win32 and UIA backends.

```bash
pyselector inspect --delay 5 --backend both --scope window
```

The output includes:

- Cursor position
- Target window information
- Win32 / UIA element attributes
- Parent hierarchy
- pywinauto selector candidates
- Hit counts and warnings
- Minimal pywinauto code snippets

## Tree

`tree` prints a compact UI element tree from either the cursor element or a window title.

```bash
pyselector tree --window-title "電卓" --backend uia --depth 3
```

## Notes

This initial version intentionally does not provide JSON output, file output, clipboard copy, GUI mode, persistent mode, or UI operations such as clicking and typing. The tool focuses on inspect, selector candidates, and hit counts.
