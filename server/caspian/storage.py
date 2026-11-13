"""Single-instance, session-scoped SQLite persistence for the demonstration."""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def encode(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


class ServiceError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        fields: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = fields

    def payload(self) -> dict:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.fields:
            error["fields"] = self.fields
        return {"error": error}


class Store:
    def __init__(self, database_path: str, clock: Callable[[], datetime] = utc_now) -> None:
        self.database_path = database_path
        self.clock = clock
        self._write_lock = threading.RLock()
        self._keeper: sqlite3.Connection | None = None
        self._uri = database_path == ":memory:"
        self._connect_path = (
            f"file:caspian-{secrets.token_hex(16)}?mode=memory&cache=shared"
            if self._uri
            else database_path
        )
        if self._uri:
            self._keeper = self.connect()
        else:
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        connection = self.connect()
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trips (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    plan_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(id, session_id)
                );
                CREATE INDEX IF NOT EXISTS trips_session ON trips(session_id);
                CREATE TABLE IF NOT EXISTS bookings (
                    reference TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    trip_plan_id TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN (
                        'draft', 'held', 'details_captured', 'payment_simulated',
                        'confirmed_simulated', 'expired', 'cancelled_simulated'
                    )),
                    expires_at TEXT NOT NULL,
                    booking_json TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    details_json TEXT,
                    inventory_released INTEGER NOT NULL DEFAULT 0 CHECK(inventory_released IN (0, 1)),
                    FOREIGN KEY(trip_plan_id, session_id) REFERENCES trips(id, session_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS bookings_session_expiry
                    ON bookings(session_id, state, expires_at);
                CREATE TABLE IF NOT EXISTS inventory (
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL CHECK(kind IN ('hotel', 'activity')),
                    resource_id TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    capacity INTEGER NOT NULL CHECK(capacity >= 0),
                    reserved INTEGER NOT NULL DEFAULT 0 CHECK(reserved >= 0 AND reserved <= capacity),
                    PRIMARY KEY(session_id, kind, resource_id, slot)
                );
                CREATE TABLE IF NOT EXISTS booking_inventory (
                    reference TEXT NOT NULL REFERENCES bookings(reference) ON DELETE CASCADE,
                    session_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    PRIMARY KEY(reference, kind, resource_id, slot),
                    FOREIGN KEY(session_id, kind, resource_id, slot)
                        REFERENCES inventory(session_id, kind, resource_id, slot) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS booking_events (
                    id INTEGER PRIMARY KEY,
                    reference TEXT NOT NULL REFERENCES bookings(reference) ON DELETE CASCADE,
                    from_state TEXT,
                    to_state TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );
                """
            )
        except BaseException:
            connection.close()
            self.close()
            raise
        # Keep WAL open between short transactions instead of checkpointing on every request.
        if self._keeper is None:
            self._keeper = connection
        else:
            connection.close()

    def now(self) -> datetime:
        return self.clock().astimezone(timezone.utc)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._connect_path,
            timeout=10,
            isolation_level=None,
            check_same_thread=False,
            uri=self._uri,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        # SQLite has one writer; a local lock avoids lock-retry storms during a demo burst.
        with self._write_lock:
            if self._keeper is None:
                self._keeper = self.connect()
            connection = self._keeper
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._purge_daily(connection)
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def _purge_daily(self, connection: sqlite3.Connection) -> None:
        today = self.now().date().isoformat()
        row = connection.execute("SELECT value FROM settings WHERE key='utc_day'").fetchone()
        if row is None or row["value"] != today:
            connection.execute("DELETE FROM sessions")
            connection.execute(
                "INSERT INTO settings(key,value) VALUES('utc_day',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (today,),
            )

    def purge(self) -> None:
        with self.transaction():
            pass

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            row = connection.execute("SELECT value FROM settings WHERE key='utc_day'").fetchone()
            if row is None or row["value"] != self.now().date().isoformat():
                self.purge()
            yield connection
        finally:
            connection.close()

    def session(self, candidate: str | None) -> tuple[str, bool, int]:
        now = self.now()
        tomorrow = datetime.combine(
            now.date() + timedelta(days=1), datetime.min.time(), timezone.utc
        )
        max_age = max(1, int((tomorrow - now).total_seconds()))
        if candidate and len(candidate) <= 64:
            with self.read() as connection:
                row = connection.execute(
                    "SELECT id FROM sessions WHERE id=? AND expires_at>?",
                    (candidate, timestamp(now)),
                ).fetchone()
                if row:
                    return row["id"], False, max_age
        with self.transaction() as connection:
            now = self.now()
            tomorrow = datetime.combine(
                now.date() + timedelta(days=1), datetime.min.time(), timezone.utc
            )
            max_age = max(1, int((tomorrow - now).total_seconds()))
            if candidate and len(candidate) <= 64:
                row = connection.execute(
                    "SELECT id FROM sessions WHERE id=? AND expires_at>?",
                    (candidate, timestamp(now)),
                ).fetchone()
                if row:
                    return row["id"], False, max_age
            session_id = secrets.token_urlsafe(32)
            connection.execute(
                "INSERT INTO sessions(id,created_at,expires_at) VALUES(?,?,?)",
                (session_id, timestamp(now), timestamp(tomorrow)),
            )
            return session_id, True, max_age

    @staticmethod
    def require_session(connection: sqlite3.Connection, session_id: str) -> None:
        if not connection.execute("SELECT 1 FROM sessions WHERE id=?", (session_id,)).fetchone():
            raise ServiceError(404, "not_found", "This demo session has expired.")

    @staticmethod
    def load_trip(connection: sqlite3.Connection, session_id: str, trip_id: str) -> dict:
        row = connection.execute(
            "SELECT plan_json FROM trips WHERE id=? AND session_id=?", (trip_id, session_id)
        ).fetchone()
        if row is None:
            raise ServiceError(404, "not_found", "Trip not found.")
        return json.loads(row["plan_json"])

    def save_trip(self, session_id: str, plan: dict) -> dict:
        with self.transaction() as connection:
            self.require_session(connection, session_id)
            connection.execute(
                "INSERT INTO trips(id,session_id,plan_json,updated_at) VALUES(?,?,?,?)",
                (plan["id"], session_id, encode(plan), timestamp(self.now())),
            )
        return plan

    def get_trip(self, session_id: str, trip_id: str) -> dict:
        with self.read() as connection:
            return self.load_trip(connection, session_id, trip_id)

    def update_trip(
        self, session_id: str, trip_id: str, update: Callable[[dict], dict]
    ) -> dict:
        with self.transaction() as connection:
            existing = self.load_trip(connection, session_id, trip_id)
            result = update(existing)
            result["id"] = existing["id"]
            result["created_at"] = existing["created_at"]
            connection.execute(
                "UPDATE trips SET plan_json=?,updated_at=? WHERE id=? AND session_id=?",
                (encode(result), timestamp(self.now()), trip_id, session_id),
            )
            return result

    def close(self) -> None:
        with self._write_lock:
            if self._keeper is not None:
                self._keeper.close()
                self._keeper = None
