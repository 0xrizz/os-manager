"""tests/test_tune_memory.py - Unit tests for MGLRU, zRAM VM sysctl, THP, and EarlyOOM memory tuning."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    audit_memory_subsystem,
    generate_mglru_config,
    generate_thp_config,
    generate_vm_sysctl_config,
)


class TestTuneMemory(unittest.TestCase):
    """Unit tests for memory subsystem configuration generation and audit."""

    def test_generate_mglru_config(self):
        """Verify MGLRU tmpfiles.d configuration generator."""
        cfg = generate_mglru_config(enabled=7, min_ttl_ms=1000)
        self.assertIn("w /sys/kernel/mm/lru_gen/enabled - - - - 7", cfg)
        self.assertIn("w /sys/kernel/mm/lru_gen/min_ttl_ms - - - - 1000", cfg)

    def test_generate_thp_config(self):
        """Verify THP tmpfiles.d configuration generator."""
        cfg = generate_thp_config(mode="madvise", defrag="defer+madvise")
        self.assertIn("w /sys/kernel/mm/transparent_hugepage/enabled - - - - madvise", cfg)
        self.assertIn("w /sys/kernel/mm/transparent_hugepage/defrag - - - - defer+madvise", cfg)

    def test_generate_vm_sysctl_config(self):
        """Verify VM sysctl configuration generator for zRAM alignment."""
        cfg = generate_vm_sysctl_config(swappiness=180, vfs_cache_pressure=50)
        self.assertIn("vm.swappiness = 180", cfg)
        self.assertIn("vm.page-cluster = 0", cfg)
        self.assertIn("vm.watermark_boost_factor = 0", cfg)
        self.assertIn("vm.watermark_scale_factor = 125", cfg)
        self.assertIn("vm.vfs_cache_pressure = 50", cfg)
        self.assertIn("vm.dirty_ratio = 10", cfg)
        self.assertIn("vm.dirty_background_ratio = 5", cfg)
        self.assertIn("vm.dirty_expire_centisecs = 3000", cfg)
        self.assertIn("vm.dirty_writeback_centisecs = 500", cfg)
        self.assertIn("fs.inotify.max_user_watches = 524288", cfg)
        self.assertIn("fs.inotify.max_user_instances = 1024", cfg)

    def test_audit_memory_subsystem(self):
        """Verify audit_memory_subsystem inspects sysfs and sysctl values."""
        with patch("pathlib.Path.read_text") as mock_read, \
             patch("pathlib.Path.is_file") as mock_is_file, \
             patch("subprocess.run") as mock_run, \
             patch("os_manager.commands.tune.audit_earlyoom_status") as mock_oom, \
             patch("os_manager.commands.tune.audit_dual_tier_swap_status") as mock_swap:
            mock_is_file.return_value = True
            mock_read.side_effect = lambda *args, **kwargs: "always [madvise] never\n"
            mock_run.return_value = MagicMock(returncode=0, stdout="180\n")
            mock_oom.return_value = {"active": True, "available": True}
            mock_swap.return_value = {"has_zram": True, "has_swapfile": True}

            res = audit_memory_subsystem()
            self.assertIn("mglru_enabled", res)
            self.assertIn("mglru_min_ttl_ms", res)
            self.assertIn("thp_mode", res)
            self.assertEqual(res["thp_mode"], "madvise")
            self.assertIn("swappiness", res)
            self.assertEqual(res["swappiness"], "180")
            self.assertTrue(res["earlyoom_active"])
            self.assertTrue(res["zram_active"])

    def test_audit_memory_subsystem_unsupported(self):
        """Verify audit_memory_subsystem handles missing sysfs gracefully."""
        with patch("pathlib.Path.is_file", return_value=False), \
             patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="")), \
             patch("os_manager.commands.tune.audit_earlyoom_status", return_value={"active": False}), \
             patch("os_manager.commands.tune.audit_dual_tier_swap_status", return_value={"has_zram": False}):
            res = audit_memory_subsystem()
            self.assertEqual(res["mglru_enabled"], "unsupported")
            self.assertEqual(res["mglru_min_ttl_ms"], "unsupported")
            self.assertEqual(res["thp_mode"], "unknown")
            self.assertEqual(res["swappiness"], "unknown")
            self.assertFalse(res["earlyoom_active"])
            self.assertFalse(res["zram_active"])

    def test_audit_memory_subsystem_includes_psi(self):
        """Verify audit_memory_subsystem includes PSI telemetry fields."""
        with patch("pathlib.Path.read_text", return_value="always [madvise] never\n"), \
             patch("pathlib.Path.is_file", return_value=True), \
             patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="180\n")), \
             patch("os_manager.commands.tune.audit_earlyoom_status", return_value={"active": True}), \
             patch("os_manager.commands.tune.audit_dual_tier_swap_status", return_value={"has_zram": True}), \
             patch("os_manager.memory.psi_daemon.audit_psi_telemetry", return_value={"supported": True, "daemon_active": True}) as mock_psi:
            res = audit_memory_subsystem()
            self.assertIn("psi", res)
            self.assertTrue(res["psi"]["supported"])
            self.assertTrue(res["psi"]["daemon_active"])

