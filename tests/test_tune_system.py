"""tests/test_tune_system.py - Unit tests for kernel sysctl, NVMe TRIM, audio, and firewall."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    audit_fstrim_timer_status,
    audit_pipewire_audio_status,
    audit_sysctl_parameters,
    audit_ufw_firewall_status,
    generate_sysctl_performance_config,
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
        self.assertEqual(res["wireplumber"], "missing")


if __name__ == "__main__":
    unittest.main()
