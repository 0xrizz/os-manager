"""tests/test_tune_kernel.py - Unit tests for Linux kernel watchdog and timer polling reduction."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    SYSCTL_KERNEL_PATH,
    audit_kernel_subsystem,
    generate_kernel_sysctl_config,
)


class TestTuneKernel(unittest.TestCase):
    """Unit tests for Linux kernel watchdog disabling, timer migration, and VM stat interval."""

    def test_generate_kernel_sysctl_config_defaults(self):
        """Verify default kernel sysctl configuration generator."""
        cfg = generate_kernel_sysctl_config()
        self.assertIn("kernel.nmi_watchdog = 0", cfg)
        self.assertIn("kernel.watchdog = 0", cfg)
        self.assertIn("vm.stat_interval = 10", cfg)
        self.assertIn("kernel.timer_migration = 0", cfg)

    def test_generate_kernel_sysctl_config_custom(self):
        """Verify customized kernel sysctl configuration generator."""
        cfg = generate_kernel_sysctl_config(
            nmi_watchdog=1,
            watchdog=1,
            vm_stat_interval=5,
            timer_migration=1,
        )
        self.assertIn("kernel.nmi_watchdog = 1", cfg)
        self.assertIn("kernel.watchdog = 1", cfg)
        self.assertIn("vm.stat_interval = 5", cfg)
        self.assertIn("kernel.timer_migration = 1", cfg)

    def test_audit_kernel_subsystem_structure(self):
        """Verify audit_kernel_subsystem returns expected dictionary keys."""
        res = audit_kernel_subsystem()
        self.assertIn("nmi_watchdog", res)
        self.assertIn("watchdog", res)
        self.assertIn("vm_stat_interval", res)
        self.assertIn("timer_migration", res)
        self.assertIn("kernel_dropin_present", res)

    def test_audit_kernel_subsystem_mocked(self):
        """Verify audit_kernel_subsystem parsing with mocked sysctl reads."""
        with patch("os_manager.commands.tune._read_sysctl") as mock_read, \
             patch("pathlib.Path.is_file") as mock_is_file:
            def mock_sysctl(key: str) -> str:
                mapping = {
                    "kernel.nmi_watchdog": "0",
                    "kernel.watchdog": "0",
                    "vm.stat_interval": "10",
                    "kernel.timer_migration": "0",
                }
                return mapping.get(key, "unknown")

            mock_read.side_effect = mock_sysctl
            mock_is_file.return_value = True

            res = audit_kernel_subsystem()
            self.assertEqual(res["nmi_watchdog"], "0")
            self.assertEqual(res["watchdog"], "0")
            self.assertEqual(res["vm_stat_interval"], "10")
            self.assertEqual(res["timer_migration"], "0")
            self.assertTrue(res["kernel_dropin_present"])


if __name__ == "__main__":
    unittest.main()
