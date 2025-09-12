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
    title TEXT NOT NULL,
    note TEXT,
    due_at INTEGER NOT NULL,    -- epoch seconds (UTC)
    created_at INTEGER NOT NULL,
    notified_at INTEGER,
    completed_at INTEGER        -- NULL if not completed, else epoch seconds (UTC)
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


def add_reminder(*, title: str, note: str | None, due_at: int) -> int:
    now = int(time.time())
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO reminders(title, note, due_at, created_at) VALUES(?,?,?,?)",
            (title, note, due_at, now),
        )
        return int(cur.lastrowid)


def list_reminders(*, include_done: bool = False):
    with connect() as conn:
        if include_done:
            # Show everything, done first by completion time, then due_at
            return list(conn.execute(
                "SELECT * FROM reminders ORDER BY "
                "CASE WHEN completed_at IS NULL THEN 0 ELSE 1 END, "
                "due_at ASC, id ASC"
            ))
        # Default: only active (not completed)
        return list(conn.execute(
            "SELECT * FROM reminders "
            "WHERE completed_at IS NULL "
            "ORDER BY due_at ASC, id ASC"
        ))


def mark_complete(reminder_id: int) -> bool:
    now = int(time.time())
    with connect() as conn:
        cur = conn.execute(
            "UPDATE reminders SET completed_at=? WHERE id=? AND completed_at IS NULL",
            (now, reminder_id),
        )
        return cur.rowcount > 0


def delete_reminder(reminder_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM reminders WHERE id=?", (reminder_id,))
        return cur.rowcount > 0


def due_unnotified(limit: int = 100):
    """Active reminders that are due and have not been notified yet."""
    now = int(time.time())
    with connect() as conn:
        return list(conn.execute(
            "SELECT * FROM reminders "
            "WHERE completed_at IS NULL "
            "  AND due_at <= ? "
            "  AND (notified_at IS NULL OR notified_at = 0) "
            "ORDER BY due_at ASC, id ASC "
            "LIMIT ?",
            (now, limit),
        ))


def due_renotify(interval_seconds: int = 24 * 60 * 60, limit: int = 500):
    """Active reminders that are due and were notified before the given interval."""
    now = int(time.time())
    threshold = now - interval_seconds
    with connect() as conn:
        return list(conn.execute(
            "SELECT * FROM reminders "
            "WHERE completed_at IS NULL "
            "  AND due_at <= ? "
            "  AND notified_at IS NOT NULL "
            "  AND notified_at > 0 "
            "  AND notified_at <= ? "
            "ORDER BY due_at ASC, id ASC "
            "LIMIT ?",
            (now, threshold, limit),
        ))


def mark_notified(reminder_id: int) -> bool:
    now = int(time.time())
    with connect() as conn:
        cur = conn.execute(
            "UPDATE reminders SET notified_at = ? WHERE id = ?",
            (now, reminder_id),
        )
        return cur.rowcount > 0


def due_active(limit: int = 500):
    """All active (not completed) reminders that are already due, regardless of notified_at."""
    now = int(time.time())
    with connect() as conn:
        return list(conn.execute(
            "SELECT * FROM reminders "
            "WHERE completed_at IS NULL "
            "  AND due_at <= ? "
            "ORDER BY due_at ASC, id ASC "
            "LIMIT ?",
            (now, limit),
        ))

