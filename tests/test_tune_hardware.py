"""tests/test_tune_hardware.py - Unit tests for Lenovo ACPI, thermals, GPU power gating, and VA-API."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    audit_gpu_runtime_power,
    audit_vaapi_acceleration,
    generate_hardware_persist_unit,
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


if __name__ == "__main__":
    unittest.main()
