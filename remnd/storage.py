from __future__ import annotations
import os
import sqlite3
import time
from pathlib import Path


APP_DIR = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "remnd"
DB_PATH = APP_DIR / "remnd.sqlite3"


SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    message TEXT NOT NULL,
    due_at INTEGER NOT NULL,    -- epoch seconds (UTC)
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_due_at ON reminders(due_at);
"""


def _ensure_dirs() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def connect() -> sqlite3.Connection:
    _ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    with conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.executescript(SCHEMA)
    return conn


def add_reminder(*, title: str | None, message: str, due_at: int) -> int:
    now = int(time.time())
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO reminders(title, message, due_at, created_at) VALUES(?,?,?,?)",
            (title, message, due_at, now),
        )
        return int(cur.lastrowid)


def list_reminders():
    with connect() as conn:
        return list(
            conn.execute("SELECT * FROM reminders ORDER BY due_at ASC, id ASC")
        )
