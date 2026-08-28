"""tests/memory/test_psi_mitigation.py - Unit tests for 3-tier PSI mitigation actions and cooldown."""

import time
import unittest
from unittest.mock import MagicMock, call, patch

from os_manager.memory.psi_daemon import (
    PsiMetrics,
    PsiReading,
    PsiThresholds,
    StagedMitigationController,
    compact_zram_devices,
    trigger_critical_cache_drop,
    trigger_mglru_kick,
)


class TestPsiMitigation(unittest.TestCase):
    """Test suite for autonomous memory mitigations and debounce mechanics."""

    def setUp(self):
        self.thresholds = PsiThresholds(
            tier1_memory_some_avg10=10.0,
            tier1_memory_some_avg60=5.0,
            tier2_memory_some_avg10=25.0,
            tier2_memory_full_avg10=10.0,
            tier3_memory_full_avg10=40.0,
            cooldown_seconds=20,
        )
        self.controller = StagedMitigationController(thresholds=self.thresholds)

    def _make_metrics(self, mem_some_10=0.0, mem_some_60=0.0, mem_full_10=0.0):
        return PsiMetrics(
            cpu_some=PsiReading(),
            memory_some=PsiReading(avg10=mem_some_10, avg60=mem_some_60),
            memory_full=PsiReading(avg10=mem_full_10),
            io_some=PsiReading(),
            io_full=PsiReading(),
        )

    def test_compact_zram_devices(self):
        """Verify zRAM compaction writes 1 to /sys/block/zram*/compact."""
        with patch("glob.glob", return_value=["/sys/block/zram0/compact", "/sys/block/zram1/compact"]), \
             patch("os_manager.memory.psi_daemon._write_privileged_sysfs", return_value=True) as mock_write:
            compacted = compact_zram_devices()
            self.assertEqual(compacted, ["/sys/block/zram0/compact", "/sys/block/zram1/compact"])
            self.assertEqual(mock_write.call_count, 2)

    def test_trigger_mglru_kick(self):
        """Verify MGLRU trigger writes to sysfs and executes sync."""
        with patch("os_manager.memory.psi_daemon._write_privileged_sysfs", return_value=True) as mock_write, \
             patch("os.sync") as mock_sync:
            res = trigger_mglru_kick()
            self.assertTrue(res)
            mock_write.assert_called_once_with("/sys/kernel/mm/lru_gen/enabled", "1")
            mock_sync.assert_called_once()

    def test_trigger_critical_cache_drop(self):
        """Verify critical drop writes drop_caches and appends log event."""
        with patch("os_manager.memory.psi_daemon._write_privileged_sysfs", return_value=True) as mock_write, \
             patch("os_manager.memory.psi_daemon._log_psi_event") as mock_log:
            res = trigger_critical_cache_drop(reason="test critical")
            self.assertTrue(res)
            mock_write.assert_called_once_with("/proc/sys/vm/drop_caches", "1")
            mock_log.assert_called_once()

    def test_evaluate_no_mitigation_when_healthy(self):
        """Verify no mitigation is executed under normal memory pressure."""
        metrics = self._make_metrics(mem_some_10=2.0, mem_some_60=1.0, mem_full_10=0.0)
        res = self.controller.evaluate_and_mitigate(metrics)
        self.assertEqual(res["tier"], "none")
        self.assertFalse(res["mitigated"])

    def test_evaluate_tier1_compact_trigger(self):
        """Verify Tier 1 compaction triggers when memory.some.avg10 >= 10.0."""
        metrics = self._make_metrics(mem_some_10=12.5, mem_some_60=2.0, mem_full_10=0.0)
        with patch("os_manager.memory.psi_daemon.compact_zram_devices", return_value=["/sys/block/zram0/compact"]):
            res = self.controller.evaluate_and_mitigate(metrics)
            self.assertEqual(res["tier"], "tier1_compact")
            self.assertTrue(res["mitigated"])
            self.assertEqual(self.controller.last_mitigation_tier, "tier1_compact")

    def test_evaluate_tier2_mglru_trigger(self):
        """Verify Tier 2 triggers compaction + MGLRU when memory.some.avg10 >= 25.0."""
        metrics = self._make_metrics(mem_some_10=28.0, mem_some_60=15.0, mem_full_10=5.0)
        with patch("os_manager.memory.psi_daemon.compact_zram_devices", return_value=["/sys/block/zram0/compact"]), \
             patch("os_manager.memory.psi_daemon.trigger_mglru_kick", return_value=True):
            res = self.controller.evaluate_and_mitigate(metrics)
            self.assertEqual(res["tier"], "tier2_mglru_sync")
            self.assertTrue(res["mitigated"])

    def test_evaluate_tier3_critical_trigger(self):
        """Verify Tier 3 triggers drop caches when memory.full.avg10 >= 40.0."""
        metrics = self._make_metrics(mem_some_10=80.0, mem_some_60=60.0, mem_full_10=45.0)
        with patch("os_manager.memory.psi_daemon.compact_zram_devices", return_value=["/sys/block/zram0/compact"]), \
             patch("os_manager.memory.psi_daemon.trigger_mglru_kick", return_value=True), \
             patch("os_manager.memory.psi_daemon.trigger_critical_cache_drop", return_value=True):
            res = self.controller.evaluate_and_mitigate(metrics)
            self.assertEqual(res["tier"], "tier3_throttle_drop")
            self.assertTrue(res["mitigated"])

    def test_cooldown_suppression(self):
        """Verify mitigation is suppressed during the 20-second cooldown window."""
        metrics = self._make_metrics(mem_some_10=15.0)
        with patch("os_manager.memory.psi_daemon.compact_zram_devices", return_value=["/sys/block/zram0/compact"]):
            # First evaluation triggers mitigation
            res1 = self.controller.evaluate_and_mitigate(metrics)
            self.assertTrue(res1["mitigated"])

            # Immediate second evaluation triggers cooldown suppression
            res2 = self.controller.evaluate_and_mitigate(metrics)
            self.assertFalse(res2["mitigated"])
            self.assertTrue(res2["cooldown_active"])
            self.assertEqual(res2["reason"], "cooldown_suppressed")
