from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SliceRun:
    agent_id: str
    finished_at: str
    status: str
    message: str


@dataclass
class BriefingRecord:
    briefing_date: str
    path: str
    slice_count: int
    status: str
    assembled_at: str


class Database:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "agent_hub.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS slice_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS briefings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    briefing_date TEXT NOT NULL UNIQUE,
                    path TEXT NOT NULL,
                    slice_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    assembled_at TEXT NOT NULL
                );
                """
            )

    def record_slice_run(self, agent_id: str, status: str, message: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO slice_runs (agent_id, finished_at, status, message)
                VALUES (?, ?, ?, ?)
                """,
                (agent_id, _utc_now(), status, message),
            )

    def latest_slice_run(self, agent_id: str) -> SliceRun | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT agent_id, finished_at, status, message
                FROM slice_runs
                WHERE agent_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (agent_id,),
            ).fetchone()
        if row is None:
            return None
        return SliceRun(**dict(row))

    def upsert_briefing(
        self,
        briefing_date: str,
        path: str,
        slice_count: int,
        status: str,
    ) -> None:
        assembled_at = _utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO briefings (briefing_date, path, slice_count, status, assembled_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(briefing_date) DO UPDATE SET
                    path = excluded.path,
                    slice_count = excluded.slice_count,
                    status = excluded.status,
                    assembled_at = excluded.assembled_at
                """,
                (briefing_date, path, slice_count, status, assembled_at),
            )

    def latest_briefing(self) -> BriefingRecord | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT briefing_date, path, slice_count, status, assembled_at
                FROM briefings
                ORDER BY assembled_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return BriefingRecord(**dict(row))
