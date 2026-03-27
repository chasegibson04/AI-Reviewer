from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class LockError(RuntimeError):
    pass


@dataclass
class LockInfo:
    path: Path
    acquired: bool
    metadata: dict[str, Any]


def _lock_dir(project_root: Path) -> Path:
    lock_dir = project_root / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir


def _is_stale(lock_path: Path, ttl_seconds: int) -> bool:
    try:
        age = time.time() - lock_path.stat().st_mtime
    except Exception:
        return False
    return age > ttl_seconds


def acquire_project_lock(
    project_root: Path,
    run_id: str,
    allow_same_project: bool,
    ttl_seconds: int,
) -> LockInfo:
    lock_path = _lock_dir(project_root) / "project.lock"
    metadata = {
        "pid": os.getpid(),
        "run_id": run_id,
        "timestamp": time.time(),
    }

    if allow_same_project:
        return LockInfo(path=lock_path, acquired=False, metadata=metadata)

    if lock_path.exists() and _is_stale(lock_path, ttl_seconds):
        try:
            lock_path.unlink()
        except Exception:
            pass

    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(metadata))
        return LockInfo(path=lock_path, acquired=True, metadata=metadata)
    except FileExistsError as exc:
        raise LockError(f"Project lock is active: {lock_path}") from exc


def release_project_lock(lock: LockInfo) -> None:
    if not lock.acquired:
        return
    try:
        lock.path.unlink()
    except FileNotFoundError:
        return
    except Exception as exc:
        raise LockError(f"Failed to release project lock: {lock.path}") from exc
