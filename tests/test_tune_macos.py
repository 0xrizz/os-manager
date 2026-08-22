"""Tests for macOS Desktop Transformation - Snapshot and Rollback."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from os_manager.commands.tune_macos import (
    apply_macos_gsettings,
    build_macos_gsettings_matrix,
    build_theme_installer_commands,
    clean_sandbox,
    create_desktop_snapshot,
    find_latest_snapshot,
    get_required_extensions,
    install_upstream_themes,
    list_desktop_snapshots,
    restore_desktop_snapshot,
    setup_apple_fonts,
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


class TestMacOSAssetEngine(unittest.TestCase):
    def test_build_theme_installer_commands(self):
        cmds = build_theme_installer_commands(accent="blue", dark=True, sandbox_dir="/tmp/test-build")
        self.assertGreaterEqual(len(cmds), 3)
        # Verify git clones & installer invocations
        flat_cmds = [" ".join(c) for c in cmds]
        self.assertTrue(any("WhiteSur-gtk-theme.git" in c for c in flat_cmds))
        self.assertTrue(any("WhiteSur-icon-theme.git" in c for c in flat_cmds))
        self.assertTrue(any("WhiteSur-cursors.git" in c for c in flat_cmds))

    @patch("subprocess.run")
    def test_install_upstream_themes_dry_run(self, mock_run):
        res = install_upstream_themes(accent="default", dark=True, dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["status"], "planned")
        self.assertGreater(len(res["planned_commands"]), 0)
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_setup_apple_fonts(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as font_dir:
            ok = setup_apple_fonts(target_dir=font_dir)
            self.assertTrue(ok)
            mock_run.assert_called_with(["fc-cache", "-f", font_dir], capture_output=True, check=False)

    def test_clean_sandbox(self):
        with tempfile.TemporaryDirectory() as tmp_d:
            sub = Path(tmp_d) / "sandbox"
            sub.mkdir()
            (sub / "dummy.txt").write_text("hello")
            self.assertTrue(sub.exists())
            self.assertTrue(clean_sandbox(str(sub)))
            self.assertFalse(sub.exists())
            # Cleaning non-existent path should return True safely
            self.assertTrue(clean_sandbox(str(sub)))

    @patch("subprocess.run")
    def test_install_upstream_themes_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        res = install_upstream_themes(accent="default", dark=True, dry_run=False)
        self.assertFalse(res["dry_run"])
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "completed")
        self.assertGreaterEqual(len(res["results"]), 3)

    @patch("subprocess.run")
    def test_install_upstream_themes_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        res = install_upstream_themes(accent="default", dark=True, dry_run=False)
        self.assertFalse(res["dry_run"])
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "failed")


class TestMacOSGSettingsAndExtensions(unittest.TestCase):
    def test_get_required_extensions(self):
        core_exts = get_required_extensions(full=False)
        full_exts = get_required_extensions(full=True)
        self.assertIn("user-theme@gnome-shell-extensions.gcampax.github.com", core_exts)
        self.assertIn("dash-to-dock@micxgx.gmail.com", core_exts)
        self.assertIn("blur-my-shell@aunetx", full_exts)
        self.assertGreater(len(full_exts), len(core_exts))

    def test_build_macos_gsettings_matrix(self):
        matrix = build_macos_gsettings_matrix(accent="default", dark=True, full=True)
        dict_matrix = {f"{s}.{k}": v for s, k, v in matrix}

        self.assertEqual(dict_matrix.get("org.gnome.desktop.wm.preferences.button-layout"), "'close,minimize,maximize:'")
        self.assertEqual(dict_matrix.get("org.gnome.desktop.interface.gtk-theme"), "'WhiteSur-Dark'")
        self.assertEqual(dict_matrix.get("org.gnome.shell.extensions.dash-to-dock.dock-position"), "'BOTTOM'")

    @patch("subprocess.run")
    def test_apply_macos_gsettings_dry_run(self, mock_run):
        res = apply_macos_gsettings(dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertGreater(len(res["settings_matrix"]), 5)
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_apply_macos_gsettings_execution(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        res = apply_macos_gsettings(dry_run=False)
        self.assertTrue(res["success"])
        self.assertGreater(mock_run.call_count, 5)


if __name__ == "__main__":
    unittest.main()
