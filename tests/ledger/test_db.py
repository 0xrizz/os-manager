"""Unit tests for SQLite WAL Ledger connection management and schema setup."""

from pathlib import Path
import tempfile
import unittest

from os_manager.ledger.db import LedgerDB


class TestLedgerDB(unittest.TestCase):
    """Verify SQLite WAL database initialization and tables."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.test_dir.name) / "test_ledger.db"
        self.db = LedgerDB(self.db_path)

    def tearDown(self) -> None:
        self.test_dir.cleanup()

    def test_wal_journal_mode_enabled(self) -> None:
        with self.db.connect() as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode;")
            mode = cur.fetchone()[0]
            self.assertEqual(mode.lower(), "wal")

    def test_schema_tables_created(self) -> None:
        with self.db.connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in cur.fetchall()]
            self.assertIn("events", tables)
            self.assertIn("locks", tables)
            self.assertIn("handoffs", tables)


if __name__ == "__main__":
    unittest.main()
