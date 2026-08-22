"""tests/test_desktop_customization.py - Unit tests for GTK bookmarks, GSettings, and Dconf."""

import os
import subprocess
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
        """Verify execution of key gsettings schemas for standard preset."""
        mock_run.return_value = MagicMock(returncode=0)
        res = apply_desktop_gsettings(preset="standard")
        self.assertTrue(all(res.values()))
        self.assertGreater(mock_run.call_count, 5)
        called_cmds = [call_args[0][0] for call_args in mock_run.call_args_list]
        self.assertTrue(any("appmenu:minimize,maximize,close" in " ".join(cmd) for cmd in called_cmds))

    @patch("subprocess.run")
    def test_apply_desktop_gsettings_macos_preset(self, mock_run):
        """Verify execution of macOS preset gsettings schemas including left traffic lights."""
        mock_run.return_value = MagicMock(returncode=0)
        res = apply_desktop_gsettings(preset="macos")
        self.assertTrue(all(res.values()))
        self.assertIn("org.gnome.desktop.wm.preferences.button-layout", res)
        self.assertIn("org.gnome.shell.extensions.dash-to-dock.dock-position", res)
        called_cmds = [call_args[0][0] for call_args in mock_run.call_args_list]
        self.assertTrue(any("close,minimize,maximize:" in " ".join(cmd) for cmd in called_cmds))
        self.assertTrue(any("org.gnome.shell.extensions.dash-to-dock" in " ".join(cmd) for cmd in called_cmds))

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

    def test_setup_desktop_env_script_help(self):
        """Verify help text of scripts/setup_desktop_env.sh."""
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "setup_desktop_env.sh"
        res = subprocess.run(["bash", str(script_path), "--help"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("macos-full", res.stdout)
        self.assertIn("--backup", res.stdout)
        self.assertIn("--restore", res.stdout)

    def test_setup_desktop_env_script_unknown_option(self):
        """Verify invalid option returns non-zero error code."""
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "setup_desktop_env.sh"
        res = subprocess.run(["bash", str(script_path), "--unknown-invalid-flag"], capture_output=True, text=True)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Unknown option", res.stderr + res.stdout)

    def test_setup_desktop_env_script_install_macos_theme(self):
        """Verify --install-macos-theme guidance output."""
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "setup_desktop_env.sh"
        res = subprocess.run(["bash", str(script_path), "--install-macos-theme"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("WhiteSur", res.stdout)


if __name__ == "__main__":
    unittest.main()
