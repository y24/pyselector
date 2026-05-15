from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pyselector.model.inspection_result import BackendInspection, InspectionResult

MAX_LOG_FILES = 20
LOG_DIR = Path("logs")
INVALID_FILENAME_CHARS = '<>:"/\\|?*'
MAX_FILENAME_PART_LENGTH = 50


def save_inspection_log(result: InspectionResult, content: str, now: datetime | None = None) -> Path:
    LOG_DIR.mkdir(exist_ok=True)
    _prune_old_logs(LOG_DIR, MAX_LOG_FILES - 1)
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    log_path = _unique_log_path(LOG_DIR / f"{timestamp}_{_filename_context(result)}.txt")
    log_path.write_text(content, encoding="utf-8")
    _prune_old_logs(LOG_DIR, MAX_LOG_FILES)
    return log_path


def _filename_context(result: InspectionResult) -> str:
    target_window_title = _value(_first_target_title(result))
    element_kind, element_title = _target_element_parts(result)
    return "_".join(
        [
            _sanitize_filename_part(target_window_title),
            _sanitize_filename_part(element_kind),
            _sanitize_filename_part(element_title),
        ]
    )


def _target_element_parts(result: InspectionResult) -> tuple[str, str]:
    uia = result.uia if result.uia and result.uia.status == "success" else None
    win32 = result.win32 if result.win32 and result.win32.status == "success" else None

    element_kind = _first_value(
        uia.element.control_type if uia and uia.element else None,
        win32.element.class_name if win32 and win32.element else None,
    )
    element_title = _first_value(
        uia.element.window_text if uia and uia.element else None,
        win32.element.window_text if win32 and win32.element else None,
    )
    return element_kind, element_title


def _first_target_title(result: InspectionResult) -> str | None:
    for inspection in _ordered_inspections(result):
        if inspection.target_window is not None and inspection.target_window.title:
            return inspection.target_window.title
    return None


def _ordered_inspections(result: InspectionResult) -> list[BackendInspection]:
    inspections: list[BackendInspection] = []
    if result.win32 is not None:
        inspections.append(result.win32)
    if result.uia is not None:
        inspections.append(result.uia)
    return inspections


def _value(value: object | None) -> str:
    return str(value).strip() if value is not None and str(value).strip() else "unknown"


def _first_value(*values: object | None) -> str:
    for value in values:
        text = _value(value)
        if text != "unknown":
            return text
    return "unknown"


def _sanitize_filename_part(value: str) -> str:
    sanitized = "".join("_" if char in INVALID_FILENAME_CHARS or ord(char) < 32 else char for char in value)
    sanitized = "_".join(sanitized.split())
    sanitized = sanitized.strip(" ._")
    if not sanitized:
        return "unknown"
    return sanitized[:MAX_FILENAME_PART_LENGTH].rstrip(" ._") or "unknown"


def _unique_log_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not create unique log file name for {path}")


def _prune_old_logs(log_dir: Path, max_files: int) -> None:
    log_files = sorted(
        (path for path in log_dir.glob("*.txt") if path.is_file()),
        key=lambda path: (path.stat().st_mtime, path.name),
    )
    for path in log_files[:-max_files]:
        path.unlink()
