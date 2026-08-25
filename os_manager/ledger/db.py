"""SQLite WAL Connection Manager and Schema Initializer."""

import os
from pathlib import Path
import sqlite3
from typing import Optional


class LedgerDB:
    """Manages SQLite database connection pool and schema lifecycle with WAL mode."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            state_dir = Path.home() / ".local" / "state" / "osm"
            state_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = state_dir / "ledger.db"

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def connect(self) -> sqlite3.Connection:
        """Create a connection with WAL mode and foreign keys enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    agent_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_topic ON events(topic, timestamp);

                CREATE TABLE IF NOT EXISTS locks (
                    resource_id TEXT PRIMARY KEY,
                    holder_agent_id TEXT NOT NULL,
                    acquired_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS handoffs (
                    handoff_id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    source_agent_id TEXT NOT NULL,
                    target_agent_id TEXT NOT NULL,
                    task_summary TEXT NOT NULL,
                    worktree_branch TEXT,
                    context_payload TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                """
            )
            conn.commit()
