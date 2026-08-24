"""tests/test_tune_audio.py - Unit tests for PipeWire low-latency audio & NVIDIA PM configuration."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    audit_audio_subsystem,
    generate_nvidia_pm_modprobe_config,
    generate_nvidia_pm_udev_rule,
    generate_pam_audio_limits_config,
    generate_pipewire_low_latency_config,
)


class TestTuneAudio(unittest.TestCase):
    """Unit tests for low-latency audio stack and NVIDIA dynamic power management generators."""

    def test_generate_pipewire_low_latency_config(self):
        """Verify generation of PipeWire 99-low-latency.conf drop-in."""
        cfg = generate_pipewire_low_latency_config(quantum=256, rate=48000)
        self.assertIn("default.clock.quantum       = 256", cfg)
        self.assertIn("default.clock.rate          = 48000", cfg)
        self.assertIn("libpipewire-module-rt", cfg)
        self.assertIn("rt.prio      = 88", cfg)
        self.assertIn("nice.level   = -11", cfg)
        self.assertIn("rtkit.enabled = true", cfg)

    def test_generate_pipewire_low_latency_config_custom_values(self):
        """Verify custom quantum and sample rate in PipeWire config."""
        cfg = generate_pipewire_low_latency_config(quantum=128, rate=96000)
        self.assertIn("default.clock.quantum       = 128", cfg)
        self.assertIn("default.clock.rate          = 96000", cfg)

    def test_generate_pam_audio_limits_config(self):
        """Verify generation of PAM real-time audio security limits."""
        cfg = generate_pam_audio_limits_config()
        self.assertIn("@audio - rtprio 95", cfg)
        self.assertIn("@audio - nice -19", cfg)
        self.assertIn("@audio - memlock unlimited", cfg)

    def test_generate_nvidia_pm_configs(self):
        """Verify NVIDIA RTD3 modprobe and udev rule generation."""
        mod_cfg = generate_nvidia_pm_modprobe_config()
        self.assertIn('options nvidia "NVreg_DynamicPowerManagement=0x02"', mod_cfg)

        udev_cfg = generate_nvidia_pm_udev_rule()
        self.assertIn('ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030000", ATTR{power/control}="auto"', udev_cfg)
        self.assertIn('ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030200", ATTR{power/control}="auto"', udev_cfg)
        self.assertIn('ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x040300", ATTR{power/control}="auto"', udev_cfg)

    def test_audit_audio_subsystem(self):
        """Verify basic structure of audit_audio_subsystem output."""
        res = audit_audio_subsystem()
        self.assertIn("pipewire_installed", res)
        self.assertIn("wireplumber_installed", res)
        self.assertIn("active_quantum", res)
        self.assertIn("active_rate", res)
        self.assertIn("low_latency_dropin_present", res)

    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("pathlib.Path.is_file")
    def test_audit_audio_subsystem_mocked(self, mock_is_file, mock_which, mock_run):
        """Verify parsing pw-dump output in audit_audio_subsystem."""
        mock_which.side_effect = lambda bin_name: f"/usr/bin/{bin_name}"
        mock_is_file.return_value = True
        mock_dump_output = """
        "default.clock.quantum": 256,
        "default.clock.rate": 48000,
        """
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_dump_output, stderr="")

        res = audit_audio_subsystem()
        self.assertTrue(res["pipewire_installed"])
        self.assertTrue(res["wireplumber_installed"])
        self.assertTrue(res["low_latency_dropin_present"])
        self.assertEqual(res["active_quantum"], "256")
        self.assertEqual(res["active_rate"], "48000")


if __name__ == "__main__":
    unittest.main()
