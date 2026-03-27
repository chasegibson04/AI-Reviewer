from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from ai_reviewer.ops.locks import LockError, acquire_project_lock, release_project_lock


def test_project_lock_acquire_release(tmp_path: Path) -> None:
    lock1 = acquire_project_lock(tmp_path, "run_a", allow_same_project=False, ttl_seconds=3600)
    assert lock1.acquired
    with pytest.raises(LockError):
        acquire_project_lock(tmp_path, "run_b", allow_same_project=False, ttl_seconds=3600)
    release_project_lock(lock1)
    lock2 = acquire_project_lock(tmp_path, "run_c", allow_same_project=False, ttl_seconds=3600)
    assert lock2.acquired
    release_project_lock(lock2)


def test_project_lock_stale_recovery(tmp_path: Path) -> None:
    lock_path = tmp_path / ".locks" / "project.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps({"pid": 9999, "run_id": "old", "timestamp": time.time() - 9999}))
    old_time = time.time() - 10_000
    os.utime(lock_path, (old_time, old_time))
    lock = acquire_project_lock(tmp_path, "run_new", allow_same_project=False, ttl_seconds=1)
    assert lock.acquired
    release_project_lock(lock)
