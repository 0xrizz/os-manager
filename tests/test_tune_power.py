"""tests/test_tune_power.py - Unit tests for dynamic dual-profile AC vs Battery power engine."""

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile

from os_manager.commands.tune import (
    generate_power_profile_udev_rule,
    apply_power_profile,
    audit_power_profile,
    run_tune,
)


class TestTunePower(unittest.TestCase):
    """Unit tests for dynamic AC / Battery power profile switching & udev generation."""

    def test_generate_power_profile_udev_rule(self):
        """Verify udev rules generator for power supply online events."""
        rule = generate_power_profile_udev_rule()
        self.assertIn('SUBSYSTEM=="power_supply"', rule)
        self.assertIn('ATTR{online}=="0"', rule)
        self.assertIn('ATTR{online}=="1"', rule)
        self.assertIn("osm tune power --profile", rule)

    def test_apply_power_profile_ac(self):
        """Verify applying AC power profile sets performance EPP, EPB, and low scheduler slice."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            res = apply_power_profile("ac")
            self.assertTrue(res["success"])
            self.assertEqual(res["profile"], "ac")
            self.assertEqual(res["epp"], "balance_performance")
            self.assertEqual(res.get("epb"), "4")
            self.assertEqual(res.get("platform_profile"), "balanced")
            self.assertEqual(res.get("sched_base_slice_ns"), 2000000)

    def test_apply_power_profile_battery(self):
        """Verify applying Battery power profile sets power-saving EPP, EPB, and high scheduler slice."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            res = apply_power_profile("battery")
            self.assertTrue(res["success"])
            self.assertEqual(res["profile"], "battery")
            self.assertEqual(res["epp"], "balance_power")
            self.assertEqual(res.get("epb"), "8")
            self.assertEqual(res.get("platform_profile"), "low-power")
            self.assertEqual(res.get("sched_base_slice_ns"), 3000000)

    def test_apply_power_profile_invalid(self):
        """Verify applying an invalid profile returns error response."""
        res = apply_power_profile("overclock")
        self.assertFalse(res["success"])
        self.assertIn("error", res)

    def test_audit_power_profile(self):
        """Verify audit_power_profile returns expected telemetry keys."""
        res = audit_power_profile()
        self.assertIn("current_epp", res)
        self.assertIn("power_source", res)
        self.assertIn("platform_profile", res)
        self.assertIn("conservation_mode", res)
        self.assertIn("fn_lock", res)

    def test_cli_tune_power_profile(self):
        """Verify CLI routing for osm tune power --profile ac."""
        with patch("os_manager.commands.tune.apply_power_profile") as mock_apply:
            mock_apply.return_value = {
                "success": True,
                "profile": "ac",
                "epp": "balance_performance",
                "sched_base_slice_ns": 2000000,
            }
            code = run_tune(["power", "--profile", "ac"])
            self.assertEqual(code, 0)
            mock_apply.assert_called_once_with("ac")

    def test_cli_tune_power_audit(self):
        """Verify CLI routing for osm tune power --audit."""
        with patch("os_manager.commands.tune.audit_power_profile") as mock_audit:
            mock_audit.return_value = {
                "current_epp": "balance_performance",
                "power_source": "ac",
                "platform_profile": "balanced",
                "conservation_mode": "enabled",
                "fn_lock": "enabled",
            }
            code = run_tune(["power", "--audit"])
            self.assertEqual(code, 0)
            mock_audit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
