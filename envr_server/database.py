"""SQLite storage for envr snapshot metadata."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class SnapshotExistsError(RuntimeError):
    """Raised when a snapshot tag already exists."""


@dataclass(slots=True)
class SnapshotRecord:
    """Metadata stored for one snapshot."""

    tag: str
    created_at: str
    lock_sha256: str
    signature: str
    public_key: str
    python_version: str
    description: str
    repo_url: str


class Database:
    """Handles metadata persistence using SQLite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def initialize(self) -> None:
        """Initialize the SQLite database and snapshots table."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    tag TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    lock_sha256 TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    python_version TEXT NOT NULL,
                    description TEXT NOT NULL,
                    repo_url TEXT NOT NULL DEFAULT ''
                )
                """
            )

    def insert_snapshot(self, record: SnapshotRecord) -> None:
        """Insert one snapshot record."""
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO snapshots (
                        tag,
                        created_at,
                        lock_sha256,
                        signature,
                        public_key,
                        python_version,
                        description,
                        repo_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.tag,
                        record.created_at,
                        record.lock_sha256,
                        record.signature,
                        record.public_key,
                        record.python_version,
                        record.description,
                        record.repo_url,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise SnapshotExistsError(record.tag) from exc

    def get_snapshot(self, tag: str) -> dict[str, Any] | None:
        """Fetch a snapshot metadata record by tag."""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    tag,
                    created_at,
                    lock_sha256,
                    signature,
                    public_key,
                    python_version,
                    description,
                    repo_url
                FROM snapshots
                WHERE tag = ?
                """,
                (tag,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_snapshots(self, prefix: str | None = None) -> list[dict[str, Any]]:
        """List metadata records with an optional tag prefix."""
        query = (
            """
            SELECT
                tag,
                created_at,
                lock_sha256,
                signature,
                public_key,
                python_version,
                description,
                repo_url
            FROM snapshots
            """
        )
        params: tuple[Any, ...] = ()
        if prefix:
            query += " WHERE tag LIKE ?"
            params = (f"{prefix}%",)
        query += " ORDER BY created_at DESC"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
