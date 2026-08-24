"""tests/test_tune_scheduler.py - Unit tests for Linux EEVDF scheduler & cgroups v2 user slices."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    audit_scheduler_subsystem,
    generate_background_slice_config,
    generate_eevdf_sysctl_config,
    generate_session_slice_config,
)


class TestTuneScheduler(unittest.TestCase):
    """Unit tests for Linux 6.6+ EEVDF scheduler slicing and cgroups v2 user slices."""

    def test_generate_eevdf_sysctl_config(self):
        """Verify sysctl configuration generator for EEVDF scheduler slicing."""
        cfg = generate_eevdf_sysctl_config(base_slice_ns=2000000, cfs_bandwidth_slice_us=3000)
        self.assertIn("kernel.sched_base_slice_ns = 2000000", cfg)
        self.assertIn("kernel.sched_cfs_bandwidth_slice_us = 3000", cfg)

    def test_generate_session_slice_config(self):
        """Verify systemd user session.slice resource override generator."""
        cfg = generate_session_slice_config(cpu_weight=500, io_weight=500)
        self.assertIn("[Slice]", cfg)
        self.assertIn("CPUWeight=500", cfg)
        self.assertIn("IOWeight=500", cfg)
        self.assertIn("ManagedOOMPreference=avoid", cfg)

    def test_generate_background_slice_config(self):
        """Verify systemd user background.slice resource override generator."""
        cfg = generate_background_slice_config(cpu_weight=20, io_weight=20, memory_high="1536M")
        self.assertIn("[Slice]", cfg)
        self.assertIn("CPUWeight=20", cfg)
        self.assertIn("IOWeight=20", cfg)
        self.assertIn("MemoryHigh=1536M", cfg)
        self.assertIn("ManagedOOMPreference=kill", cfg)

    def test_audit_scheduler_subsystem(self):
        """Verify audit_scheduler_subsystem returns expected structure."""
        res = audit_scheduler_subsystem()
        self.assertIn("base_slice_ns", res)
        self.assertIn("session_slice_configured", res)
        self.assertIn("background_slice_configured", res)

    def test_audit_scheduler_subsystem_mocked(self):
        """Verify audit_scheduler_subsystem with mocked sysctl and slice path files."""
        with patch("subprocess.run") as mock_run, \
             patch("pathlib.Path.is_file") as mock_is_file:
            mock_run.return_value = MagicMock(returncode=0, stdout="2000000\n")
            mock_is_file.return_value = True

            res = audit_scheduler_subsystem()
            self.assertEqual(res["base_slice_ns"], "2000000")
            self.assertTrue(res["session_slice_configured"])
            self.assertTrue(res["background_slice_configured"])

    def test_audit_scheduler_subsystem_failure(self):
        """Verify audit_scheduler_subsystem fallback when sysctl fails and files are missing."""
        with patch("subprocess.run") as mock_run, \
             patch("pathlib.Path.is_file", return_value=False):
            mock_run.return_value = MagicMock(returncode=1, stdout="")

            res = audit_scheduler_subsystem()
            self.assertEqual(res["base_slice_ns"], "unknown")
            self.assertFalse(res["session_slice_configured"])
            self.assertFalse(res["background_slice_configured"])


if __name__ == "__main__":
    unittest.main()
