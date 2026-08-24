from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pyselector import __version__
from pyselector.record.model import Recording, RecordedStep
from pyselector.server.state import state_dir
from pyselector.utils.errors import ArgumentError

RECORDING_FILE_NAME = "recording.json"


def recording_path() -> Path:
    """記録の置き場所。

    デスクトップは共有資源で、同時に 2 つの操作シナリオを記録することはできない。
    したがって記録はユーザーにつき 1 つとし、サーバーの状態ファイルと同じ場所に置く
    （設計 11 §3.4）。常駐サーバー経由で実行しても同じファイルを指す。
    """
    return state_dir() / RECORDING_FILE_NAME


def is_recording() -> bool:
    """記録中かどうか。

    記録していないときのコストがこの 1 回のファイル存在確認だけで済むよう、
    act / expect はまずこれを見てから重い処理に入る（設計 11 §8.2）。
    """
    try:
        return recording_path().exists()
    except OSError:
        return False


def start(name: str) -> Recording:
    recording = Recording(
        name=name,
        started_at=datetime.now().isoformat(timespec="seconds"),
        version=__version__,
    )
    save(recording)
    return recording


def load() -> Recording | None:
    path = recording_path()
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ArgumentError(f"記録ファイルを読めません: {path}: {exc}") from exc
    except OSError as exc:
        raise ArgumentError(f"記録ファイルを読めません: {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ArgumentError(f"記録ファイルの形式が不正です: {path}")
    return Recording.from_dict(raw)


def save(recording: Recording) -> Path:
    path = recording_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(recording.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def append(build_step) -> RecordedStep | None:
    """記録中であれば 1 手順を追加する。

    ``build_step`` は連番を受け取って :class:`RecordedStep` を返す呼び出し可能。
    記録していないときに手順を組み立てる無駄を避けるため、値ではなく関数で受け取る。
    """
    recording = load()
    if recording is None:
        return None
    step = build_step(recording.next_seq)
    save(Recording(
        name=recording.name,
        started_at=recording.started_at,
        version=recording.version,
        steps=[*recording.steps, step],
    ))
    return step


def clear() -> bool:
    path = recording_path()
    if not path.exists():
        return False
    path.unlink()
    return True
