import os
from datetime import datetime

from pyselector.model.element_info import ElementInfo
from pyselector.model.inspection_result import BackendInspection, CursorPosition, InspectionResult
from pyselector.model.target_window import TargetWindowInfo
from pyselector.output import log_file


def test_save_inspection_log_uses_requested_filename_parts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = InspectionResult(
        cursor_position=CursorPosition(10, 20),
        win32=BackendInspection(
            backend="win32",
            element=ElementInfo(backend="win32", window_text="OK", class_name="Button"),
            target_window=TargetWindowInfo(backend="win32", title="電卓:Main", handle=100),
        ),
        uia=BackendInspection(
            backend="uia",
            element=ElementInfo(backend="uia", window_text="1/2", control_type="Button"),
            target_window=TargetWindowInfo(backend="uia", title="電卓:Main", handle=100),
        ),
    )

    path = log_file.save_inspection_log(result, "RESULT", datetime(2026, 5, 15, 23, 1, 2))

    assert path.parent.resolve() == tmp_path / "logs"
    assert path.name == "20260515_230102_電卓_Main_Button_1_2.txt"
    assert path.read_text(encoding="utf-8") == "RESULT"


def test_save_inspection_log_falls_back_to_win32_parts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = InspectionResult(
        cursor_position=CursorPosition(10, 20),
        win32=BackendInspection(
            backend="win32",
            element=ElementInfo(backend="win32", window_text="OK", class_name="Button"),
            target_window=TargetWindowInfo(backend="win32", title="Window", handle=100),
        ),
    )

    path = log_file.save_inspection_log(result, "RESULT", datetime(2026, 5, 15, 23, 1, 2))

    assert path.name == "20260515_230102_Window_Button_OK.txt"


def test_save_inspection_log_falls_back_to_win32_kind_without_losing_uia_title(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = InspectionResult(
        cursor_position=CursorPosition(10, 20),
        win32=BackendInspection(
            backend="win32",
            element=ElementInfo(backend="win32", window_text="Win32 Title", class_name="Button"),
            target_window=TargetWindowInfo(backend="win32", title="Window", handle=100),
        ),
        uia=BackendInspection(
            backend="uia",
            element=ElementInfo(backend="uia", window_text="UIA Title"),
            target_window=TargetWindowInfo(backend="uia", title="Window", handle=100),
        ),
    )

    path = log_file.save_inspection_log(result, "RESULT", datetime(2026, 5, 15, 23, 1, 2))

    assert path.name == "20260515_230102_Window_Button_UIA_Title.txt"


def test_save_inspection_log_omits_missing_filename_parts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = InspectionResult(
        cursor_position=CursorPosition(10, 20),
        uia=BackendInspection(
            backend="uia",
            element=ElementInfo(backend="uia", control_type="Button"),
        ),
    )

    path = log_file.save_inspection_log(result, "RESULT", datetime(2026, 5, 15, 23, 1, 2))

    assert path.name == "20260515_230102_Button.txt"
    assert "unknown" not in path.name


def test_save_inspection_log_prunes_oldest_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logs = tmp_path / "logs"
    logs.mkdir()
    for index in range(20):
        path = logs / f"old-{index:02}.txt"
        path.write_text(str(index), encoding="utf-8")
        timestamp = 1000 + index
        os.utime(path, (timestamp, timestamp))
    result = InspectionResult(cursor_position=CursorPosition(10, 20))

    log_file.save_inspection_log(result, "RESULT", datetime(2026, 5, 15, 23, 1, 2))

    names = sorted(path.name for path in logs.glob("*.txt"))
    assert len(names) == 20
    assert "old-00.txt" not in names
    assert "20260515_230102.txt" in names


def test_save_inspection_log_does_not_overwrite_same_second_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = InspectionResult(cursor_position=CursorPosition(10, 20))
    now = datetime(2026, 5, 15, 23, 1, 2)

    first = log_file.save_inspection_log(result, "FIRST", now)
    second = log_file.save_inspection_log(result, "SECOND", now)

    assert first.name == "20260515_230102.txt"
    assert second.name == "20260515_230102_1.txt"
    assert first.read_text(encoding="utf-8") == "FIRST"
    assert second.read_text(encoding="utf-8") == "SECOND"
