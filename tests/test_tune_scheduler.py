"""tests/test_tune_scheduler.py - Unit tests for Linux EEVDF scheduler & sched_ext dynamic eBPF scheduler."""

import json
import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    audit_scheduler_subsystem,
    generate_background_slice_config,
    generate_eevdf_sysctl_config,
    generate_session_slice_config,
)
from os_manager.scheduler.scx import ScxSupportStatus


class TestTuneScheduler(unittest.TestCase):
    """Unit tests for Linux 6.6+ EEVDF scheduler slicing, cgroups v2 user slices, and sched_ext."""

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

    @patch("os_manager.commands.tune.probe_sched_ext_support")
    def test_audit_scheduler_subsystem_includes_scx(self, mock_probe):
        """Verify audit_scheduler_subsystem includes sched_ext capability block."""
        mock_probe.return_value = ScxSupportStatus(
            kernel_supported=True,
            sysfs_present=True,
            active_scheduler="lavd",
            installed_schedulers=["scx_lavd"],
            service_active=True,
            service_enabled=True,
            details="sched_ext active (enabled)",
        )
        res = audit_scheduler_subsystem()
        self.assertIn("base_slice_ns", res)
        self.assertIn("session_slice_configured", res)
        self.assertIn("background_slice_configured", res)
        self.assertIn("sched_ext", res)
        self.assertTrue(res["sched_ext"]["kernel_supported"])
        self.assertEqual(res["sched_ext"]["active_scheduler"], "lavd")


if __name__ == "__main__":
    unittest.main()
