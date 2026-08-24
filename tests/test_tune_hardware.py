"""tests/test_tune_hardware.py - Unit tests for Lenovo ACPI, thermals, GPU power gating, and VA-API."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    audit_gpu_runtime_power,
    audit_hardware_state,
    audit_vaapi_acceleration,
    configure_hardware_persistence,
    generate_hardware_persist_unit,
    generate_hardware_persistence_config,
    generate_hardware_persistence_service,
    get_battery_conservation_status,
    get_fn_lock_status,
    get_platform_profile,
    set_battery_conservation_mode,
    set_fn_lock_mode,
    set_platform_profile,
)


class TestTuneHardware(unittest.TestCase):
    """Unit tests for Lenovo hardware power and GPU tuning."""

    def test_battery_conservation_status_reading(self):
        """Verify reading battery conservation mode from mock sysfs."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("1\n")
            f.flush()
            sysfs_path = f.name

        try:
            status = get_battery_conservation_status(sysfs_path=sysfs_path)
            self.assertEqual(status, "enabled")
        finally:
            os.remove(sysfs_path)

    def test_battery_conservation_missing_sysfs(self):
        """Verify handling of missing sysfs node on non-IdeaPad hardware."""
        status = get_battery_conservation_status(sysfs_path="/tmp/nonexistent_sysfs_node")
        self.assertEqual(status, "unsupported")

    @patch("subprocess.run")
    def test_set_battery_conservation_enable(self, mock_run):
        """Verify setting battery conservation mode calls tee."""
        mock_run.return_value = MagicMock(returncode=0)
        success = set_battery_conservation_mode(enable=True, sysfs_path="/tmp/mock_node")
        self.assertTrue(success)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertEqual(args[0], "tee")
        self.assertIn("/tmp/mock_node", args)

    def test_platform_profile_reading(self):
        """Verify reading ACPI platform profile."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("balanced\n")
            f.flush()
            prof_path = f.name

        try:
            prof = get_platform_profile(profile_path=prof_path)
            self.assertEqual(prof, "balanced")
        finally:
            os.remove(prof_path)

    @patch("subprocess.run")
    def test_set_platform_profile_valid(self, mock_run):
        """Verify setting valid platform profile."""
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f_choices:
            f_choices.write("low-power balanced performance\n")
            f_choices.flush()
            choices_path = f_choices.name

        try:
            success = set_platform_profile("performance", profile_path="/tmp/prof", choices_path=choices_path)
            self.assertTrue(success)
        finally:
            os.remove(choices_path)

    def test_fn_lock_status_reading(self):
        """Verify reading fn-lock status."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("1\n")
            f.flush()
            fn_path = f.name

        try:
            status = get_fn_lock_status(fn_path=fn_path)
            self.assertEqual(status, "enabled")
        finally:
            os.remove(fn_path)

    def test_gpu_runtime_power_suspended(self):
        """Verify GPU power status parsing."""
        temp_dir = tempfile.TemporaryDirectory()
        try:
            status_file = Path(temp_dir.name) / "runtime_status"
            status_file.write_text("suspended\n")
            control_file = Path(temp_dir.name) / "control"
            control_file.write_text("auto\n")

            res = audit_gpu_runtime_power(gpu_pci_path=temp_dir.name)
            self.assertTrue(res["available"])
            self.assertEqual(res["runtime_status"], "suspended")
            self.assertTrue(res["power_saving"])
        finally:
            temp_dir.cleanup()

    @patch("subprocess.run")
    def test_audit_vaapi_acceleration_present(self, mock_run):
        """Verify VA-API driver detection via vainfo."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="vainfo: VA-API version: 1.22 (libva 2.22.0)\nvainfo: Driver version: Intel i965 driver for Intel(R) Ironlake",
            stderr="",
        )
        with patch("shutil.which", return_value="/usr/bin/vainfo"):
            res = audit_vaapi_acceleration()
            self.assertTrue(res["available"])
            self.assertIn("VA-API version", res["details"])

    def test_generate_hardware_persist_unit(self):
        """Verify generation of systemd unit for hardware persistence."""
        unit = generate_hardware_persist_unit(conf_path="/etc/osm/hardware-tune.conf")
        self.assertIn("[Unit]", unit)
        self.assertIn("Description=os-manager Lenovo Hardware Power & ACPI Tuning Persistence", unit)
        self.assertIn("WantedBy=multi-user.target", unit)

    def test_generate_hardware_persistence_config(self):
        """Verify hardware persistence configuration file format."""
        cfg = generate_hardware_persistence_config(conservation=True, fn_lock=True, gpu_power="auto")
        self.assertIn("CONSERVATION_MODE=1", cfg)
        self.assertIn("FN_LOCK=1", cfg)
        self.assertIn("GPU_POWER_SAVE=auto", cfg)

    def test_generate_hardware_persistence_config_custom(self):
        """Verify hardware persistence configuration with disabled/custom flags."""
        cfg = generate_hardware_persistence_config(conservation=False, fn_lock=False, gpu_power="on")
        self.assertIn("CONSERVATION_MODE=0", cfg)
        self.assertIn("FN_LOCK=0", cfg)
        self.assertIn("GPU_POWER_SAVE=on", cfg)

    def test_generate_hardware_persistence_service(self):
        """Verify systemd service unit definition for hardware persistence."""
        unit = generate_hardware_persistence_service()
        self.assertIn("[Unit]", unit)
        self.assertIn("osm-hardware-tune", unit)
        self.assertIn("ExecStart=", unit)

    @patch("subprocess.run")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.mkdir")
    @patch("os.geteuid", return_value=0)
    def test_configure_hardware_persistence_enable_root(self, mock_geteuid, mock_mkdir, mock_write, mock_run):
        """Verify configure_hardware_persistence writes config & service unit as root."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        success = configure_hardware_persistence(
            enable=True,
            config_path="/etc/osm/hardware-tune.conf",
            service_path="/etc/systemd/system/osm-hardware-tune.service",
        )
        self.assertTrue(success)
        self.assertEqual(mock_write.call_count, 2)
        self.assertEqual(mock_run.call_count, 2)

    @patch("subprocess.run")
    @patch("os.geteuid", return_value=1000)
    def test_configure_hardware_persistence_enable_non_root(self, mock_geteuid, mock_run):
        """Verify configure_hardware_persistence uses sudo when running as non-root."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        success = configure_hardware_persistence(
            enable=True,
            config_path="/etc/osm/hardware-tune.conf",
            service_path="/etc/systemd/system/osm-hardware-tune.service",
        )
        self.assertTrue(success)
        # sudo mkdir -p (conf), sudo tee (conf), sudo mkdir -p (srv), sudo tee (srv), daemon-reload, enable
        self.assertTrue(mock_run.call_count >= 4)

    @patch("subprocess.run")
    @patch("pathlib.Path.unlink")
    @patch("pathlib.Path.is_file", return_value=True)
    @patch("os.geteuid", return_value=0)
    def test_configure_hardware_persistence_disable_root(self, mock_geteuid, mock_is_file, mock_unlink, mock_run):
        """Verify configure_hardware_persistence disables and removes service unit as root."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        success = configure_hardware_persistence(
            enable=False,
            service_path="/etc/systemd/system/osm-hardware-tune.service",
        )
        self.assertTrue(success)
        mock_unlink.assert_called_once()
        self.assertEqual(mock_run.call_count, 2)

    @patch("subprocess.run")
    @patch("os.geteuid", return_value=1000)
    def test_configure_hardware_persistence_disable_non_root(self, mock_geteuid, mock_run):
        """Verify configure_hardware_persistence uses sudo to disable service as non-root."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        success = configure_hardware_persistence(
            enable=False,
            service_path="/etc/systemd/system/osm-hardware-tune.service",
        )
        self.assertTrue(success)
        self.assertEqual(mock_run.call_count, 3)

    def test_audit_hardware_state_via_hal(self):
        """Verify audit_hardware_state queries active HAL driver."""
        state = audit_hardware_state()
        self.assertIn("conservation_mode", state)
        self.assertIn("platform_profile", state)
        self.assertIn("platform_profile_choices", state)
        self.assertIn("gpu_power_control", state)
        self.assertIn("gpu_runtime_status", state)
        self.assertIn("dmi_vendor", state)
        self.assertIn("dmi_product", state)


if __name__ == "__main__":
    unittest.main()
