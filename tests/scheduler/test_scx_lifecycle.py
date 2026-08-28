"""tests/scheduler/test_scx_lifecycle.py - Unit tests for sched_ext profile registry, lifecycle ops, and systemd unit generator."""

import unittest
from unittest.mock import MagicMock, patch
from os_manager.scheduler.scx import (
    SCX_PROFILES,
    ScxProfile,
    ScxSupportStatus,
    generate_scx_systemd_unit,
)


class TestScxProfilesAndGenerator(unittest.TestCase):
    """Test suite for SCX profile definitions and systemd unit file generation."""

    def test_scx_profiles_registry_contents(self):
        """Verify standard sched_ext profiles are registered with correct binary names."""
        expected_profiles = ["lavd", "bpfland", "rusty", "central", "simple"]
        for name in expected_profiles:
            self.assertIn(name, SCX_PROFILES)
            prof = SCX_PROFILES[name]
            self.assertIsInstance(prof, ScxProfile)
            self.assertEqual(prof.name, name)
            self.assertTrue(prof.binary_name.startswith("scx_"))
            self.assertTrue(len(prof.description) > 0)
            self.assertTrue(len(prof.recommended_for) > 0)

    def test_generate_scx_systemd_unit_basic(self):
        """Verify systemd unit generation with default arguments."""
        unit = generate_scx_systemd_unit("/usr/bin/scx_lavd")
        self.assertIn("[Unit]", unit)
        self.assertIn("Description=sched_ext eBPF Kernel Scheduler", unit)
        self.assertIn("ConditionPathExists=/sys/kernel/sched_ext", unit)
        self.assertIn("[Service]", unit)
        self.assertIn("ExecStart=/usr/bin/scx_lavd", unit)
        self.assertIn("LimitMEMLOCK=infinity", unit)
        self.assertIn("Restart=on-failure", unit)
        self.assertIn("[Install]", unit)
        self.assertIn("WantedBy=multi-user.target", unit)

    def test_generate_scx_systemd_unit_with_args(self):
        """Verify systemd unit generation with custom profile arguments."""
        unit = generate_scx_systemd_unit("/usr/local/bin/scx_bpfland", ["--performance", "-v"])
        self.assertIn("ExecStart=/usr/local/bin/scx_bpfland --performance -v", unit)

    @patch("shutil.which")
    @patch("subprocess.run")
    @patch("os_manager.scheduler.scx.probe_sched_ext_support")
    def test_start_scx_scheduler_success_systemd(self, mock_probe, mock_run, mock_which):
        """Test starting a scheduler via systemd service."""
        from os_manager.scheduler.scx import ScxSupportStatus, start_scx_scheduler

        mock_probe.return_value = ScxSupportStatus(
            kernel_supported=True,
            sysfs_present=True,
            active_scheduler=None,
            installed_schedulers=["scx_lavd"],
        )
        mock_which.return_value = "/usr/bin/scx_lavd"
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        res = start_scx_scheduler(profile="lavd", runtime_only=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["profile"], "lavd")
        self.assertEqual(res["mode"], "systemd")

    @patch("os_manager.scheduler.scx.probe_sched_ext_support")
    def test_start_scx_scheduler_unsupported_kernel(self, mock_probe):
        """Test start_scx_scheduler gracefully refusing when kernel is unsupported."""
        from os_manager.scheduler.scx import ScxSupportStatus, start_scx_scheduler

        mock_probe.return_value = ScxSupportStatus(
            kernel_supported=False,
            sysfs_present=False,
            active_scheduler=None,
            details="Stock kernel detected",
        )

        res = start_scx_scheduler(profile="lavd")
        self.assertFalse(res["success"])
        self.assertIn("Stock kernel detected", res["error"])

    @patch("shutil.which", return_value=None)
    @patch("os_manager.scheduler.scx.probe_sched_ext_support")
    def test_start_scx_scheduler_missing_binary(self, mock_probe, mock_which):
        """Test start_scx_scheduler failing when scheduler binary is not installed."""
        from os_manager.scheduler.scx import ScxSupportStatus, start_scx_scheduler

        mock_probe.return_value = ScxSupportStatus(
            kernel_supported=True,
            sysfs_present=True,
            active_scheduler=None,
        )

        res = start_scx_scheduler(profile="rusty")
        self.assertFalse(res["success"])
        self.assertIn("Binary 'scx_rusty' not found", res["error"])

    @patch("subprocess.run")
    def test_stop_scx_scheduler(self, mock_run):
        """Test stopping sched_ext scheduler and returning to EEVDF."""
        from os_manager.scheduler.scx import stop_scx_scheduler

        mock_run.return_value = MagicMock(returncode=0, stdout="")
        res = stop_scx_scheduler()
        self.assertTrue(res["success"])
        self.assertIn("EEVDF fallback active", res["message"])

    @patch("shutil.which", return_value="/usr/bin/scx_bpfland")
    @patch("subprocess.run")
    @patch("os_manager.scheduler.scx.probe_sched_ext_support")
    def test_enable_and_disable_scx_service(self, mock_probe, mock_run, mock_which):
        """Test enabling and disabling persistent systemd scx service."""
        from os_manager.scheduler.scx import ScxSupportStatus, disable_scx_service, enable_scx_service

        mock_probe.return_value = ScxSupportStatus(
            kernel_supported=True,
            sysfs_present=True,
            active_scheduler=None,
        )
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        en_res = enable_scx_service(profile="bpfland")
        self.assertTrue(en_res["success"])

        dis_res = disable_scx_service()
        self.assertTrue(dis_res["success"])


if __name__ == "__main__":
    unittest.main()
