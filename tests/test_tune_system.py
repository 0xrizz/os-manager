"""tests/test_tune_system.py - Unit tests for kernel sysctl, NVMe TRIM, audio, and firewall."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    audit_fstrim_timer_status,
    audit_ntfs_mount_driver,
    audit_pipewire_audio_status,
    audit_sysctl_parameters,
    audit_ufw_firewall_status,
    generate_fstab_ntfs3_entry,
    generate_sysctl_performance_config,
    migrate_ntfs_driver,
)


class TestTuneSystem(unittest.TestCase):
    """Unit tests for system kernel and security tuning."""

    def test_generate_sysctl_performance_config(self):
        """Verify generated sysctl configuration contains required performance keys."""
        cfg = generate_sysctl_performance_config()
        self.assertIn("vm.swappiness = 10", cfg)
        self.assertIn("vm.vfs_cache_pressure = 50", cfg)
        self.assertIn("fs.inotify.max_user_watches = 524288", cfg)
        self.assertIn("net.ipv4.tcp_congestion_control = bbr", cfg)

    @patch("subprocess.run")
    def test_audit_sysctl_parameters_active(self, mock_run):
        """Verify audit of active sysctl keys."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="10\n"),
            MagicMock(returncode=0, stdout="524288\n"),
            MagicMock(returncode=0, stdout="bbr\n"),
        ]
        res = audit_sysctl_parameters()
        self.assertEqual(res["swappiness"], "10")
        self.assertEqual(res["inotify_watches"], "524288")
        self.assertEqual(res["congestion_control"], "bbr")

    @patch("subprocess.run")
    def test_audit_sysctl_parameters_failure(self, mock_run):
        """Verify audit of active sysctl keys handles failure."""
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout=""),
            MagicMock(returncode=1, stdout=""),
            MagicMock(returncode=1, stdout=""),
        ]
        res = audit_sysctl_parameters()
        self.assertEqual(res["swappiness"], "unknown")
        self.assertEqual(res["inotify_watches"], "unknown")
        self.assertEqual(res["congestion_control"], "unknown")

    @patch("subprocess.run")
    def test_audit_fstrim_timer_active(self, mock_run):
        """Verify fstrim.timer inspection when active."""
        mock_run.return_value = MagicMock(returncode=0, stdout="active\n")
        res = audit_fstrim_timer_status()
        self.assertTrue(res["active"])

    @patch("subprocess.run")
    def test_audit_fstrim_timer_inactive(self, mock_run):
        """Verify fstrim.timer inspection when inactive."""
        mock_run.return_value = MagicMock(returncode=3, stdout="inactive\n")
        res = audit_fstrim_timer_status()
        self.assertFalse(res["active"])

    @patch("subprocess.run")
    @patch("shutil.which")
    def test_audit_ufw_firewall_status_active(self, mock_which, mock_run):
        """Verify UFW firewall status parsing when active and default deny."""
        mock_which.return_value = "/usr/sbin/ufw"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Status: active\nDefault: deny (incoming), allow (outgoing), disabled (routed)",
        )
        res = audit_ufw_firewall_status()
        self.assertTrue(res["available"])
        self.assertTrue(res["active"])
        self.assertTrue(res["default_deny_incoming"])

    @patch("shutil.which")
    def test_audit_ufw_firewall_not_installed(self, mock_which):
        """Verify UFW audit when ufw binary is not present."""
        mock_which.return_value = None
        res = audit_ufw_firewall_status()
        self.assertFalse(res["available"])
        self.assertFalse(res["active"])
        self.assertFalse(res["default_deny_incoming"])

    @patch("shutil.which")
    def test_audit_pipewire_audio_status_present(self, mock_which):
        """Verify PipeWire session manager status check when present."""
        def side_which(binary: str):
            if binary == "pipewire":
                return "/usr/bin/pipewire"
            if binary == "wireplumber":
                return "/usr/bin/wireplumber"
            return None

        mock_which.side_effect = side_which
        res = audit_pipewire_audio_status()
        self.assertTrue(res["available"])
        self.assertEqual(res["pipewire"], "/usr/bin/pipewire")
        self.assertEqual(res["wireplumber"], "/usr/bin/wireplumber")

    @patch("shutil.which")
    def test_audit_pipewire_audio_status_missing(self, mock_which):
        """Verify PipeWire session manager status check when missing."""
        mock_which.return_value = None
        res = audit_pipewire_audio_status()
        self.assertFalse(res["available"])
        self.assertEqual(res["pipewire"], "missing")
    def test_generate_fstab_ntfs3_entry_success(self):
        """Verify replacing ntfs-3g with ntfs3 in fstab content."""
        sample_fstab = (
            "UUID=3E01-3117 /boot/efi vfat defaults,noatime 0 2\n"
            "UUID=6C7AB7E37AB7A7EA /mnt/data ntfs-3g defaults,uid=1000,gid=1000,umask=022,nofail 0 0\n"
        )
        updated = generate_fstab_ntfs3_entry(sample_fstab, mount_point="/mnt/data")
        self.assertIn("ntfs3", updated)
        self.assertNotIn("ntfs-3g", updated)
        self.assertIn(
            "UUID=6C7AB7E37AB7A7EA /mnt/data ntfs3 defaults,uid=1000,gid=1000,umask=022,nofail,iocharset=utf8 0 0",
            updated,
        )

    def test_audit_ntfs_mount_driver(self):
        """Verify detection of in-kernel ntfs3 vs ntfs-3g FUSE mount."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ntfs3\n")
            res = audit_ntfs_mount_driver("/mnt/data")
            self.assertEqual(res["driver"], "ntfs3")
            self.assertTrue(res["is_inkernel"])

    @patch("subprocess.run")
    @patch("shutil.copy2")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.is_file")
    def test_migrate_ntfs_driver_success(self, mock_isfile, mock_read, mock_write, mock_copy, mock_run):
        """Verify successful ntfs-3g to ntfs3 migration with backup and remount."""
        mock_isfile.return_value = True
        mock_read.return_value = "UUID=123 /mnt/data ntfs-3g defaults 0 0\n"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = migrate_ntfs_driver(fstab_path="/tmp/fstab", mount_point="/mnt/data")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "migrated")
        self.assertIn(".bak.", res["backup"])
        mock_copy.assert_called_once()
        mock_write.assert_called_once()
        mock_run.assert_called_once_with(["mount", "-o", "remount", "/mnt/data"], capture_output=True, text=True, check=False)

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.is_file")
    def test_migrate_ntfs_driver_already_migrated(self, mock_isfile, mock_read):
        """Verify idempotency when fstab is already using ntfs3."""
        mock_isfile.return_value = True
        mock_read.return_value = "UUID=123 /mnt/data ntfs3 defaults,iocharset=utf8 0 0\n"

        res = migrate_ntfs_driver(fstab_path="/tmp/fstab", mount_point="/mnt/data")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "already_migrated")

    @patch("subprocess.run")
    @patch("shutil.copy2")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.is_file")
    def test_migrate_ntfs_driver_rollback_on_failure(self, mock_isfile, mock_read, mock_write, mock_copy, mock_run):
        """Verify automatic rollback to backup if remount fails."""
        mock_isfile.return_value = True
        mock_read.return_value = "UUID=123 /mnt/data ntfs-3g defaults 0 0\n"
        # First remount fails, second remount during rollback succeeds
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="", stderr="mount error: wrong fs type"),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]

        res = migrate_ntfs_driver(fstab_path="/tmp/fstab", mount_point="/mnt/data")
        self.assertFalse(res["success"])
        self.assertTrue(res.get("rolled_back", False))
        self.assertIn("Remount failed, rolled back", res["error"])
        # Check that copy was called twice: once for backup, once for restore
        self.assertEqual(mock_copy.call_count, 2)


if __name__ == "__main__":
    unittest.main()
