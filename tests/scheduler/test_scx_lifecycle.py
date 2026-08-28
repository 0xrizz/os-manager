"""tests/scheduler/test_scx_lifecycle.py - Unit tests for sched_ext profile registry, lifecycle ops, and systemd unit generator."""

import unittest
from unittest.mock import MagicMock, patch
from os_manager.scheduler.scx import (
    SCX_PROFILES,
    ScxProfile,
    ScxSupportStatus,
    disable_scx_service,
    enable_scx_service,
    generate_scx_systemd_unit,
    start_scx_scheduler,
    stop_scx_scheduler,
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

    @patch("os_manager.scheduler.scx.probe_sched_ext_support")
    @patch("shutil.which")
    @patch("os_manager.scheduler.scx._run_privileged")
    def test_start_scx_scheduler_systemd_success(self, mock_sudo, mock_which, mock_probe):
        """Verify successful activation of sched_ext scheduler via systemd."""
        mock_probe.return_value = ScxSupportStatus(
            kernel_supported=True,
            sysfs_present=True,
            active_scheduler=None,
        )
        mock_which.return_value = "/usr/bin/scx_lavd"
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_sudo.return_value = mock_proc

        res = start_scx_scheduler(profile="lavd", runtime_only=False)
        self.assertTrue(res["success"])
        self.assertEqual(res["profile"], "lavd")
        self.assertEqual(res["mode"], "systemd")

    @patch("os_manager.scheduler.scx.probe_sched_ext_support")
    def test_start_scx_scheduler_unsupported_kernel_fails(self, mock_probe):
        """Verify start fails gracefully with descriptive error when kernel lacks support."""
        mock_probe.return_value = ScxSupportStatus(
            kernel_supported=False,
            sysfs_present=False,
            active_scheduler=None,
            details="Stock kernel detected.",
        )
        res = start_scx_scheduler(profile="lavd")
        self.assertFalse(res["success"])
        self.assertIn("Kernel does not support sched_ext", res["error"])

    @patch("shutil.which", return_value=None)
    @patch("os_manager.scheduler.scx.probe_sched_ext_support")
    def test_start_scx_scheduler_missing_binary(self, mock_probe, mock_which):
        """Test start_scx_scheduler failing when scheduler binary is not installed."""
        mock_probe.return_value = ScxSupportStatus(
            kernel_supported=True,
            sysfs_present=True,
            active_scheduler=None,
        )

        res = start_scx_scheduler(profile="rusty")
        self.assertFalse(res["success"])
        self.assertIn("Binary 'scx_rusty' not found", res["error"])

    @patch("subprocess.Popen")
    @patch("shutil.which", return_value="/usr/bin/scx_lavd")
    @patch("os_manager.scheduler.scx.probe_sched_ext_support")
    def test_start_scx_scheduler_runtime_only(self, mock_probe, mock_which, mock_popen):
        """Test starting scheduler in runtime-only detached background mode."""
        mock_probe.return_value = ScxSupportStatus(
            kernel_supported=True,
            sysfs_present=True,
            active_scheduler=None,
        )
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        res = start_scx_scheduler(profile="lavd", runtime_only=True)
        self.assertTrue(res["success"])
        self.assertEqual(res["mode"], "runtime")
        self.assertEqual(res["pid"], 12345)

    @patch("os_manager.scheduler.scx._run_privileged")
    def test_stop_scx_scheduler(self, mock_sudo):
        """Verify stop routine issues systemctl stop and pkill."""
        mock_sudo.return_value = MagicMock(returncode=0)
        res = stop_scx_scheduler()
        self.assertTrue(res["success"])
        self.assertIn("Linux default EEVDF fallback active", res["message"])

    @patch("shutil.which", return_value="/usr/bin/scx_bpfland")
    @patch("os_manager.scheduler.scx._run_privileged")
    @patch("os_manager.scheduler.scx.probe_sched_ext_support")
    def test_enable_and_disable_scx_service(self, mock_probe, mock_sudo, mock_which):
        """Test enabling and disabling persistent systemd scx service."""
        mock_probe.return_value = ScxSupportStatus(
            kernel_supported=True,
            sysfs_present=True,
            active_scheduler=None,
        )
        mock_sudo.return_value = MagicMock(returncode=0, stdout="", stderr="")
        en_res = enable_scx_service(profile="bpfland")
        self.assertTrue(en_res["success"])

        dis_res = disable_scx_service()
        self.assertTrue(dis_res["success"])

    @patch("subprocess.run")
    def test_run_privileged_wrapper(self, mock_run):
        """Test _run_privileged helper with sudo_exec or fallback."""
        from os_manager.scheduler.scx import _run_privileged
        mock_run.return_value = MagicMock(returncode=0)
        res = _run_privileged(["systemctl", "status", "scx"])
        self.assertEqual(res.returncode, 0)
        self.assertTrue(mock_run.called)

    def test_package_all_exports(self):
        """Verify scheduler package exposes public API symbols."""
        import os_manager.scheduler as pkg
        for symbol in [
            "ScxProfile",
            "ScxProfileName",
            "ScxSupportStatus",
            "SCX_PROFILES",
            "SYSTEMD_SCX_UNIT_PATH",
            "generate_scx_systemd_unit",
            "discover_installed_schedulers",
            "probe_sched_ext_support",
            "start_scx_scheduler",
            "stop_scx_scheduler",
            "enable_scx_service",
            "disable_scx_service",
        ]:
            self.assertTrue(hasattr(pkg, symbol), f"Missing exported symbol: {symbol}")



if __name__ == "__main__":
    unittest.main()
