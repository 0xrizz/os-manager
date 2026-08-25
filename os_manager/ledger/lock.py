"""Distributed Advisory Mutex Locking Engine with SQLite TTL."""

from pathlib import Path
import time
from typing import Optional

from .db import LedgerDB


class DistributedLock:
    """Distributed resource mutex supporting timeouts and automatic expiration."""

    def __init__(
        self,
        resource_id: str,
        agent_id: str,
        ttl_seconds: float = 30.0,
        db: Optional[LedgerDB] = None,
    ):
        self.resource_id = resource_id
        self.agent_id = agent_id
        self.ttl_seconds = ttl_seconds
        self.db = db or LedgerDB()
        self._acquired = False

    def acquire(self, blocking: bool = True, timeout: float = 5.0) -> bool:
        """Attempt to acquire advisory lock before timeout expires."""
        start = time.time()
        while True:
            now = time.time()
            expires_at = now + self.ttl_seconds

            with self.db.connect() as conn:
                cur = conn.cursor()
                # Clean up expired locks
                cur.execute(
                    "DELETE FROM locks WHERE resource_id = ? AND expires_at < ?",
                    (self.resource_id, now),
                )

                try:
                    cur.execute(
                        """
                        INSERT INTO locks (resource_id, holder_agent_id, acquired_at, expires_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (self.resource_id, self.agent_id, now, expires_at),
                    )
                    conn.commit()
                    self._acquired = True
                    return True
                except Exception:
                    # Lock currently held by another active agent
                    pass

            if not blocking:
                return False

            if time.time() - start >= timeout:
                return False

            time.sleep(0.05)

    def release(self) -> bool:
        """Release the advisory lock held by this agent."""
        with self.db.connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM locks WHERE resource_id = ? AND holder_agent_id = ?",
                (self.resource_id, self.agent_id),
            )
            conn.commit()
            self._acquired = False
            return cur.rowcount > 0

    def is_locked(self) -> bool:
        """Check if resource is currently locked by any active agent."""
        now = time.time()
        with self.db.connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM locks WHERE resource_id = ? AND expires_at >= ?",
                (self.resource_id, now),
            )
            return cur.fetchone() is not None

    def __enter__(self) -> "DistributedLock":
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock on {self.resource_id}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
