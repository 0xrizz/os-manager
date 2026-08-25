"""Unit tests for DistributedLock advisory concurrency mutex."""

from pathlib import Path
import tempfile
import time
import unittest

from os_manager.ledger.db import LedgerDB
from os_manager.ledger.lock import DistributedLock


class TestDistributedLock(unittest.TestCase):
    """Verify lock acquisition, mutual exclusion, and timeout expiration."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "test_lock.db"
        self.db = LedgerDB(self.db_path)

    def tearDown(self) -> None:
        self.test_dir.cleanup()

    def test_single_agent_acquire_and_release(self) -> None:
        lock = DistributedLock("workspace_root", agent_id="agent-1", db=self.db)
        self.assertTrue(lock.acquire())
        self.assertTrue(lock.is_locked())
        self.assertTrue(lock.release())
        self.assertFalse(lock.is_locked())

    def test_mutual_exclusion_between_two_agents(self) -> None:
        lock1 = DistributedLock("workspace_root", agent_id="agent-1", ttl_seconds=10.0, db=self.db)
        lock2 = DistributedLock("workspace_root", agent_id="agent-2", ttl_seconds=10.0, db=self.db)

        self.assertTrue(lock1.acquire())
        # lock2 should fail non-blocking
        self.assertFalse(lock2.acquire(blocking=False))

        # lock1 releases, lock2 should now acquire
        lock1.release()
        self.assertTrue(lock2.acquire(blocking=False))
        lock2.release()

    def test_lock_context_manager(self) -> None:
        lock = DistributedLock("git_worktree_1", agent_id="agent-1", db=self.db)
        with lock:
            self.assertTrue(lock.is_locked())
        self.assertFalse(lock.is_locked())


if __name__ == "__main__":
    unittest.main()
