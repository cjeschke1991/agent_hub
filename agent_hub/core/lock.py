from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class LockInfo:
    pid: int
    created_at: float


class BriefingLockError(RuntimeError):
    pass


def _read_lock(path: Path) -> LockInfo | None:
    if not path.exists():
        return None
    try:
        pid_str, created_at_str = path.read_text(encoding="utf-8").strip().split(",", 1)
        return LockInfo(pid=int(pid_str), created_at=float(created_at_str))
    except (OSError, ValueError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@contextmanager
def briefing_lock(
    lockfile: Path,
    wait_seconds: float = 10.0,
    *,
    force: bool = False,
) -> Iterator[None]:
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    if force:
        info = _read_lock(lockfile)
        if info and not _pid_alive(info.pid):
            lockfile.unlink(missing_ok=True)
        wait_seconds = 0.0
    deadline = time.time() + wait_seconds

    while True:
        try:
            fd = os.open(lockfile, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"{os.getpid()},{time.time()}")
            break
        except FileExistsError:
            info = _read_lock(lockfile)
            if info and not _pid_alive(info.pid):
                lockfile.unlink(missing_ok=True)
                continue
            if time.time() >= deadline:
                holder = info.pid if info else "unknown"
                raise BriefingLockError(f"Briefing assemble already running (pid {holder})")
            time.sleep(0.2)

    try:
        yield
    finally:
        lockfile.unlink(missing_ok=True)
