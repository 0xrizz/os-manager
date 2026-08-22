"""tests/test_desktop_customization.py - Unit tests for GTK bookmarks, GSettings, and Dconf."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    add_nautilus_bookmark,
    apply_desktop_gsettings,
    dconf_dump_desktop,
    dconf_load_desktop,
    get_nautilus_bookmarks,
)


class TestDesktopCustomization(unittest.TestCase):
    """Unit tests for GNOME bookmarks and desktop setup."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.bookmark_file = Path(self.temp_dir.name) / "bookmarks"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_add_nautilus_bookmark_creation(self):
        """Verify bookmark addition to fresh GTK 3 bookmarks file."""
        success = add_nautilus_bookmark("file:///mnt/data", "Data Store", str(self.bookmark_file))
        self.assertTrue(success)
        bookmarks = get_nautilus_bookmarks(str(self.bookmark_file))
        self.assertIn("file:///mnt/data Data Store", bookmarks)

    def test_add_nautilus_bookmark_idempotency(self):
        """Verify duplicate bookmarks are prevented."""
        add_nautilus_bookmark("file:///mnt/data", "Data Store", str(self.bookmark_file))
        add_nautilus_bookmark("file:///mnt/data", "Data Store", str(self.bookmark_file))
        bookmarks = get_nautilus_bookmarks(str(self.bookmark_file))
        self.assertEqual(len(bookmarks), 1)

    def test_get_nautilus_bookmarks_nonexistent_file(self):
        """Verify get_nautilus_bookmarks returns empty list for nonexistent file."""
        nonexistent = Path(self.temp_dir.name) / "does_not_exist"
        self.assertEqual(get_nautilus_bookmarks(str(nonexistent)), [])

    @patch("subprocess.run")
    def test_apply_desktop_gsettings(self, mock_run):
        """Verify execution of key gsettings schemas."""
        mock_run.return_value = MagicMock(returncode=0)
        res = apply_desktop_gsettings()
        self.assertTrue(all(res.values()))
        self.assertGreater(mock_run.call_count, 5)

    @patch("subprocess.run")
    def test_dconf_dump_and_load(self, mock_run):
        """Verify dconf dump and load invocations."""
        mock_run.return_value = MagicMock(returncode=0)
        dump_target = Path(self.temp_dir.name) / "mock_dconf.ini"
        dump_ok = dconf_dump_desktop(str(dump_target))
        self.assertTrue(dump_ok)
        load_ok = dconf_load_desktop(str(dump_target))
        self.assertTrue(load_ok)

    def test_dconf_load_nonexistent_file(self):
        """Verify dconf_load_desktop returns False if file does not exist."""
        nonexistent = Path(self.temp_dir.name) / "nonexistent.ini"
        self.assertFalse(dconf_load_desktop(str(nonexistent)))


if __name__ == "__main__":
    unittest.main()
