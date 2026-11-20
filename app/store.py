"""Idempotency store: which (source, externalId) pairs were already accepted.

Why SQLite: one file in a Docker volume, part of Python's standard library, no database server to run.
It is enough for one app instance; with several instances this table would move to Postgres or Redis.
The calls take microseconds, so they run inline in the async endpoints.
"""

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

SCHEMA = """
CREATE TABLE IF NOT EXISTS intake (
    source      TEXT NOT NULL,
    external_id TEXT NOT NULL,
    lead_id     TEXT NOT NULL,
    state       TEXT NOT NULL CHECK (state IN ('pending', 'forwarded')),
    received_at TEXT NOT NULL,
    PRIMARY KEY (source, external_id)
)
"""


@dataclass(frozen=True)
class Reservation:
    lead_id: str
    # new: go on and forward it; forwarded: already handed to n8n earlier (a duplicate);
    # pending: another request with this id is being forwarded right now.
    outcome: Literal["new", "forwarded", "pending"]


class IdempotencyStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False + a lock: FastAPI may call from different threads.
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(SCHEMA)
        self._lock = threading.Lock()

    def reserve(self, source: str, external_id: str, received_at: datetime) -> Reservation:
        """Claims the id atomically: INSERT OR IGNORE either inserts (new) or finds the row that is already there."""
        lead_id = str(uuid.uuid4())
        with self._lock:
            inserted = self._db.execute(
                "INSERT OR IGNORE INTO intake (source, external_id, lead_id, state, received_at) "
                "VALUES (?, ?, ?, 'pending', ?)",
                (source, external_id, lead_id, received_at.isoformat()),
            ).rowcount
            if inserted:
                return Reservation(lead_id, "new")
            row = self._db.execute(
                "SELECT lead_id, state FROM intake WHERE source = ? AND external_id = ?", (source, external_id)
            ).fetchone()
        return Reservation(row[0], row[1])

    def mark_forwarded(self, source: str, external_id: str) -> None:
        with self._lock:
            self._db.execute(
                "UPDATE intake SET state = 'forwarded' WHERE source = ? AND external_id = ?", (source, external_id)
            )

    def release(self, source: str, external_id: str) -> None:
        """Forwarding failed: forget the id, so the source's retry is processed as new and nothing is lost."""
        with self._lock:
            self._db.execute(
                "DELETE FROM intake WHERE source = ? AND external_id = ? AND state = 'pending'", (source, external_id)
            )

    def close(self) -> None:
        self._db.close()
