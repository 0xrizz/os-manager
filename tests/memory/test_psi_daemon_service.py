"""tests/memory/test_psi_daemon_service.py - Unit tests for PSI monitor engine and systemd unit lifecycle."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.memory.psi_daemon import (
    PsiMonitorEngine,
    SYSTEMD_PSI_UNIT_PATH,
    audit_psi_telemetry,
    generate_psi_systemd_unit,
    manage_psi_daemon,
)


class TestPsiDaemonService(unittest.TestCase):
    """Test suite for monitor loop, systemd unit generation, and service management."""

    def test_generate_psi_systemd_unit(self):
        """Verify systemd service unit template content."""
        unit = generate_psi_systemd_unit()
        self.assertIn("[Unit]", unit)
        self.assertIn("Description=os-manager Autonomous PSI Memory Feedback & zRAM Compaction Daemon", unit)
        self.assertIn("ExecStart=/usr/local/bin/osm psi daemon --run", unit)
        self.assertIn("Restart=always", unit)
        self.assertIn("MemoryMax=128M", unit)

    def test_manage_psi_daemon_status_inactive(self):
        """Verify manage_psi_daemon status check when service is inactive."""
        with patch("subprocess.run") as mock_run, \
             patch("pathlib.Path.is_file", return_value=True):
            mock_run.side_effect = [
                MagicMock(returncode=3, stdout="inactive\n"),  # is-active
                MagicMock(returncode=0, stdout="enabled\n"),   # is-enabled
            ]
            res = manage_psi_daemon("status")
            self.assertTrue(res["installed"])
            self.assertFalse(res["active"])
            self.assertTrue(res["enabled"])

    def test_manage_psi_daemon_start(self):
        """Verify manage_psi_daemon start writes unit and starts service."""
        with patch("os_manager.memory.psi_daemon._write_privileged_sysfs", return_value=True) as mock_write, \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            res = manage_psi_daemon("start")
            self.assertTrue(res["success"])
            mock_write.assert_called_once()

    def test_manage_psi_daemon_stop(self):
        """Verify manage_psi_daemon stop calls systemctl stop."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            res = manage_psi_daemon("stop")
            self.assertTrue(res["success"])

    def test_audit_psi_telemetry(self):
        """Verify audit_psi_telemetry collects subsystem health and PSI readings."""
        with patch("os_manager.memory.psi_daemon.collect_psi_metrics") as mock_metrics, \
             patch("glob.glob", return_value=["/sys/block/zram0/compact"]), \
             patch("os_manager.memory.psi_daemon.manage_psi_daemon", return_value={"active": True, "installed": True}):
            mock_metrics.return_value = MagicMock(
                cpu_some=MagicMock(avg10=1.0, avg60=2.0, avg300=3.0),
                memory_some=MagicMock(avg10=4.0, avg60=5.0, avg300=6.0),
                memory_full=MagicMock(avg10=7.0, avg60=8.0, avg300=9.0),
                io_some=MagicMock(avg10=10.0, avg60=11.0, avg300=12.0),
                io_full=MagicMock(avg10=13.0, avg60=14.0, avg300=15.0),
                timestamp="2026-08-28T10:00:00Z",
            )
            telemetry = audit_psi_telemetry()
            self.assertTrue(telemetry["supported"])
            self.assertTrue(telemetry["daemon_active"])
            self.assertEqual(telemetry["cpu"]["some_avg10"], 1.0)
            self.assertEqual(telemetry["memory"]["some_avg10"], 4.0)
            self.assertEqual(telemetry["memory"]["full_avg10"], 7.0)
            self.assertEqual(telemetry["zram_devices"], ["/sys/block/zram0/compact"])

    def test_psi_monitor_engine_step(self):
        """Verify PsiMonitorEngine step executes a single poll & mitigate iteration."""
        with patch("os_manager.memory.psi_daemon.collect_psi_metrics") as mock_metrics:
            mock_metrics.return_value = MagicMock(
                memory_some=MagicMock(avg10=15.0, avg60=2.0),
                memory_full=MagicMock(avg10=0.0),
            )
            engine = PsiMonitorEngine()
            with patch.object(engine.controller, "evaluate_and_mitigate", return_value={"mitigated": True, "tier": "tier1_compact"}) as mock_eval:
                result = engine.step()
                self.assertIsNotNone(result)
                mock_eval.assert_called_once()
