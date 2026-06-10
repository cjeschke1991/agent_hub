from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from agent_hub.core.config import HubConfig, load_config


def pinball_data_dir(config: HubConfig | None = None) -> Path:
    config = config or load_config()
    return config.data_dir / "pinball"


def pinball_db_path(config: HubConfig | None = None) -> Path:
    return pinball_data_dir(config) / "pinball.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS machines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    manufacturer TEXT,
    year INTEGER,
    edition TEXT,
    ruleset TEXT,
    description TEXT,
    location TEXT,
    notes TEXT,
    opdb_id TEXT,
    external_metadata_json TEXT,
    image_path TEXT,
    rulesheet_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS maintenance_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    entry_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    due_date TEXT,
    completed_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id INTEGER NOT NULL REFERENCES machines(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    priority TEXT DEFAULT 'medium',
    estimated_cost REAL,
    parts TEXT,
    install_notes TEXT,
    before_after_notes TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'want_to_learn',
    tags TEXT,
    notes TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_maintenance_machine ON maintenance_entries(machine_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_status ON maintenance_entries(status);
CREATE INDEX IF NOT EXISTS idx_maintenance_type ON maintenance_entries(entry_type);
CREATE INDEX IF NOT EXISTS idx_mods_machine ON mods(machine_id);
CREATE INDEX IF NOT EXISTS idx_mods_status ON mods(status);
CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status);
"""


def _migrate_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(machines)").fetchall()}
    if "image_path" not in columns:
        conn.execute("ALTER TABLE machines ADD COLUMN image_path TEXT")
    if "rulesheet_url" not in columns:
        conn.execute("ALTER TABLE machines ADD COLUMN rulesheet_url TEXT")


def init_db(config: HubConfig | None = None) -> Path:
    path = pinball_db_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate_schema(conn)
    return path


def images_dir(config: HubConfig | None = None) -> Path:
    return pinball_data_dir(config) / "images"


@contextmanager
def connect(db_path: Path | None = None, config: HubConfig | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or pinball_db_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
