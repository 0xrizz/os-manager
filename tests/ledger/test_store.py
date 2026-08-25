"""Unit tests for EventStore event logging and query operations."""

from pathlib import Path
import tempfile
import unittest

from os_manager.ledger.db import LedgerDB
from os_manager.ledger.store import AgentEvent, EventStore


class TestEventStore(unittest.TestCase):
    """Verify event append and topic query capabilities."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "test_store.db"
        self.db = LedgerDB(self.db_path)
        self.store = EventStore(self.db)

    def tearDown(self) -> None:
        self.test_dir.cleanup()

    def test_append_and_query_event(self) -> None:
        event = AgentEvent(
            event_id="evt_001",
            timestamp=1700000000.0,
            agent_id="claude-code",
            topic="workspace.build",
            payload={"status": "success", "duration_ms": 120},
        )
        self.store.append_event(event)

        results = self.store.query_events(topic="workspace.build")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].event_id, "evt_001")
        self.assertEqual(results[0].payload.get("status"), "success")


if __name__ == "__main__":
    unittest.main()
