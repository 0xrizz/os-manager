"""tests/scheduler/test_scx_lifecycle.py - Unit tests for sched_ext profile registry and systemd unit generator."""

import unittest
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


if __name__ == "__main__":
    unittest.main()
