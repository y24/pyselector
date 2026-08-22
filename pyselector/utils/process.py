from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from functools import lru_cache

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_IMAGE_PATH_LENGTH = 32768


@lru_cache(maxsize=256)
def get_process_name(process_id: int | None) -> str | None:
    """PID から実行ファイル名を取得する。

    tasklist の起動は環境によっては数十秒かかるため、Win32 API を直接呼ぶ。
    取得できない場合（他ユーザーや保護されたプロセスなど）は None を返す。
    """
    if process_id is None or process_id <= 0:
        return None
    if os.name != "nt":
        return None
    kernel32 = _kernel32()
    if kernel32 is None:
        return None
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(MAX_IMAGE_PATH_LENGTH)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return os.path.basename(buffer.value) or None
    except Exception:
        return None
    finally:
        kernel32.CloseHandle(handle)


@lru_cache(maxsize=1)
def _kernel32() -> ctypes.WinDLL | None:
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        return kernel32
    except Exception:
        return None
