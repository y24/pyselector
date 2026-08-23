from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

STATE_DIR_ENV_VAR = "PYSELECTOR_STATE_DIR"
STATE_FILE_NAME = "server.json"
#: 削除が一時的に拒否されたときの再試行回数と間隔（最大 2 秒）。
#: 実測では、書いた直後のファイルをウイルス対策ソフトが握っていて
#: WinError 32 になることがある。
CLEAR_ATTEMPTS = 100
CLEAR_WAIT_SECONDS = 0.02


@dataclass(frozen=True)
class ServerState:
    """稼働中サーバーの覚え書き。

    接続そのものにこのファイルは要らない（パイプ名は SID から決まる）。
    ``--status`` / ``--stop`` と、常駐していることを目に見えるようにするために置く。
    """

    pid: int
    pipe: str
    instance_id: str
    version: str
    started_at: str
    allow_actions: bool = False
    idle_timeout: int = 300

    def to_dict(self) -> dict[str, object]:
        return {
            "pid": self.pid,
            "pipe": self.pipe,
            "instance_id": self.instance_id,
            "version": self.version,
            "started_at": self.started_at,
            "allow_actions": self.allow_actions,
            "idle_timeout": self.idle_timeout,
        }


def state_dir() -> Path:
    """状態ファイルの置き場所。

    テストが実ユーザーの %LOCALAPPDATA% を汚さないよう、環境変数で差し替えられる。
    """
    override = os.environ.get(STATE_DIR_ENV_VAR)
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "pyselector"
    return Path.home() / ".pyselector"


def state_path() -> Path:
    return state_dir() / STATE_FILE_NAME


def write_state(state: ServerState) -> Path:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_state() -> ServerState | None:
    path = state_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return ServerState(
            pid=int(raw["pid"]),
            pipe=str(raw["pipe"]),
            instance_id=str(raw.get("instance_id", "")),
            version=str(raw.get("version", "")),
            started_at=str(raw.get("started_at", "")),
            allow_actions=bool(raw.get("allow_actions", False)),
            idle_timeout=int(raw.get("idle_timeout", 300)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def clear_state(attempts: int = CLEAR_ATTEMPTS, wait: float = CLEAR_WAIT_SECONDS) -> bool:
    """状態ファイルを消す。消えていればそのまま真を返す。

    Windows では、書いた直後のファイルを別のプロセス（ウイルス対策やインデクサ）が
    握っていて削除を拒まれることがある。短く再試行する。
    それでも残った場合は、pid が死んでいる状態ファイルとして read_live_state が掃除する。
    """
    path = state_path()
    for attempt in range(attempts):
        try:
            path.unlink()
            return True
        except FileNotFoundError:
            return True
        except OSError:
            if attempt == attempts - 1:
                return not path.exists()
            time.sleep(wait)
    return False


def read_live_state() -> ServerState | None:
    """生きているサーバーの状態だけを返す。

    pid が既に居なければ、古い状態ファイルをその場で掃除する（設計 5.4）。
    """
    state = read_state()
    if state is None:
        return None
    if not is_process_alive(state.pid):
        clear_state()
        return None
    return state


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import win32api
        import win32con
        import win32event
    except ImportError:
        return _is_process_alive_posix(pid)
    try:
        handle = win32api.OpenProcess(win32con.SYNCHRONIZE, False, pid)
    except Exception:
        return False
    try:
        # 終了済みプロセスのハンドルはシグナル状態になる。
        return win32event.WaitForSingleObject(handle, 0) != win32event.WAIT_OBJECT_0
    finally:
        try:
            handle.Close()
        except Exception:
            pass


def _is_process_alive_posix(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")
