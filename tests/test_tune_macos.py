"""Tests for macOS Desktop Transformation - Snapshot and Rollback."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from os_manager.commands.tune_macos import (
    create_desktop_snapshot,
    find_latest_snapshot,
    list_desktop_snapshots,
    restore_desktop_snapshot,
)


class TestMacOSSnapshotAndRollback(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.backup_dir = Path(self.temp_dir.name) / "backups"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("subprocess.run")
    def test_create_desktop_snapshot(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        snapshot_path = create_desktop_snapshot(str(self.backup_dir))
        self.assertIsNotNone(snapshot_path)
        self.assertTrue(Path(snapshot_path).name.startswith("desktop-"))
        self.assertTrue(snapshot_path.endswith(".dconf"))

    @patch("subprocess.run")
    def test_create_desktop_snapshot_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        snapshot_path = create_desktop_snapshot(str(self.backup_dir))
        self.assertIsNone(snapshot_path)

    @patch("subprocess.run")
    def test_create_desktop_snapshot_exception(self, mock_run):
        mock_run.side_effect = OSError("dconf command not found")
        snapshot_path = create_desktop_snapshot(str(self.backup_dir))
        self.assertIsNone(snapshot_path)

    def test_list_desktop_snapshots(self):
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        f1 = self.backup_dir / "desktop-20260822-100000.dconf"
        f2 = self.backup_dir / "desktop-20260822-110000.dconf"
        other = self.backup_dir / "other-file.txt"
        f1.touch()
        f2.touch()
        other.touch()

        snapshots = list_desktop_snapshots(str(self.backup_dir))
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0].name, "desktop-20260822-110000.dconf")
        self.assertEqual(snapshots[1].name, "desktop-20260822-100000.dconf")

    def test_find_latest_snapshot(self):
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        f1 = self.backup_dir / "desktop-20260822-100000.dconf"
        f2 = self.backup_dir / "desktop-20260822-110000.dconf"
        f1.touch()
        f2.touch()

        latest = find_latest_snapshot(str(self.backup_dir))
        self.assertIsNotNone(latest)
        self.assertEqual(latest.name, "desktop-20260822-110000.dconf")

    def test_find_latest_snapshot_empty(self):
        latest = find_latest_snapshot(str(self.backup_dir))
        self.assertIsNone(latest)

    @patch("subprocess.run")
    def test_restore_desktop_snapshot_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        snap = self.backup_dir / "desktop-test.dconf"
        snap.touch()

        ok = restore_desktop_snapshot(str(snap))
        self.assertTrue(ok)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[:3], ["dconf", "load", "/org/gnome/"])

    @patch("subprocess.run")
    def test_restore_latest_snapshot_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        snap = self.backup_dir / "desktop-20260822-120000.dconf"
        snap.touch()

        ok = restore_desktop_snapshot(backup_dir=str(self.backup_dir))
        self.assertTrue(ok)
        mock_run.assert_called_once()

    def test_restore_nonexistent_snapshot(self):
        ok = restore_desktop_snapshot("/path/to/nonexistent/snapshot.dconf")
        self.assertFalse(ok)

    def test_restore_no_snapshots_found(self):
        ok = restore_desktop_snapshot(backup_dir=str(self.backup_dir))
        self.assertFalse(ok)

    @patch("subprocess.run")
    def test_restore_desktop_snapshot_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        snap = self.backup_dir / "desktop-test.dconf"
        snap.touch()

        ok = restore_desktop_snapshot(str(snap))
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
