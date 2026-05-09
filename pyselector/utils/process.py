from __future__ import annotations

import os
import subprocess


def get_process_name(process_id: int | None) -> str | None:
    if process_id is None:
        return None
    if os.name != "nt":
        return None
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {process_id}", "/FO", "CSV", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None
    if not output or "INFO:" in output:
        return None
    return output.split(",", 1)[0].strip('"') or None
