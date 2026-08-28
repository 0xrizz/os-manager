"""tests/test_tune_cpu.py - Unit tests for declarative CPU slice configuration and audit."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    BACKGROUND_CPUSET_SLICE_PATH,
    SESSION_CPUSET_SLICE_PATH,
    audit_cpu_subsystem,
    generate_background_cpuset_config,
    generate_session_cpuset_config,
)
from os_manager.cpu.topology import CpuTopology


class TestTuneCpuSubsystem(unittest.TestCase):
    """Test suite for declarative systemd cgroups v2 slice generation and audit."""

    def test_generate_session_cpuset_config_default(self):
        """Verify generation of session.slice cpuset drop-in."""
        cfg = generate_session_cpuset_config("0-3,8-11")
        self.assertIn("[Slice]", cfg)
        self.assertIn("AllowedCPUs=0-3,8-11", cfg)

    def test_generate_background_cpuset_config_default(self):
        """Verify generation of background.slice cpuset drop-in."""
        cfg = generate_background_cpuset_config("4-7")
        self.assertIn("[Slice]", cfg)
        self.assertIn("AllowedCPUs=4-7", cfg)

    def test_audit_cpu_subsystem_structure(self):
        """Verify audit_cpu_subsystem returns structured topology and drop-in status."""
        mock_topo = CpuTopology(
            total_cpus=8,
            is_heterogeneous=True,
            detection_method="core_type",
            p_cores=[0, 1, 2, 3],
            e_cores=[4, 5, 6, 7],
            p_core_mask="0-3",
            e_core_mask="4-7",
            all_cores_mask="0-7",
        )
        with patch("os_manager.commands.tune.detect_cpu_topology", return_value=mock_topo), \
             patch("pathlib.Path.is_file", return_value=True):
            audit = audit_cpu_subsystem()
            self.assertEqual(audit["total_cpus"], 8)
            self.assertTrue(audit["is_heterogeneous"])
            self.assertEqual(audit["detection_method"], "core_type")
            self.assertEqual(audit["p_core_mask"], "0-3")
            self.assertEqual(audit["e_core_mask"], "4-7")
            self.assertTrue(audit["session_cpuset_configured"])
            self.assertTrue(audit["background_cpuset_configured"])

    @patch("subprocess.run")
    def test_cli_tune_cpu_apply(self, mock_run):
        """Verify osm tune cpu --apply writes cpuset drop-ins and reloads systemd."""
        mock_run.return_value = MagicMock(returncode=0)
        from os_manager.commands.tune import run_tune

        ret = run_tune(["cpu", "--apply"])
        self.assertEqual(ret, 0)
        self.assertTrue(mock_run.called)

    def test_cli_tune_cpu_dry_run(self):
        """Verify osm tune cpu --dry-run outputs plan without making changes."""
        from os_manager.commands.tune import run_tune

        ret = run_tune(["cpu", "--dry-run"])
        self.assertEqual(ret, 0)

