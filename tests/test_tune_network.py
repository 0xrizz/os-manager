"""tests/test_tune_network.py - Unit tests for Linux network & socket subsystem tuning."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.tune import (
    SYSCTL_NETWORK_PATH,
    audit_network_subsystem,
    generate_network_sysctl_config,
)


class TestTuneNetwork(unittest.TestCase):
    """Unit tests for Linux network stack, TCP BBR, fq_codel, and socket optimization."""

    def test_generate_network_sysctl_config_defaults(self):
        """Verify default network sysctl configuration generator."""
        cfg = generate_network_sysctl_config()
        self.assertIn("net.core.default_qdisc = fq_codel", cfg)
        self.assertIn("net.ipv4.tcp_congestion_control = bbr", cfg)
        self.assertIn("net.ipv4.tcp_fastopen = 3", cfg)
        self.assertIn("net.ipv4.tcp_slow_start_after_idle = 0", cfg)
        self.assertIn("net.core.somaxconn = 8192", cfg)
        self.assertIn("net.ipv4.tcp_max_syn_backlog = 8192", cfg)
        self.assertIn("net.ipv4.tcp_tw_reuse = 1", cfg)
        self.assertIn("net.ipv4.tcp_fin_timeout = 15", cfg)
        self.assertIn("net.ipv4.tcp_notsent_lowat = 16384", cfg)

    def test_generate_network_sysctl_config_custom(self):
        """Verify customized network sysctl configuration generator."""
        cfg = generate_network_sysctl_config(
            congestion_control="cubic",
            qdisc="cake",
            fastopen=1,
            somaxconn=4096,
        )
        self.assertIn("net.core.default_qdisc = cake", cfg)
        self.assertIn("net.ipv4.tcp_congestion_control = cubic", cfg)
        self.assertIn("net.ipv4.tcp_fastopen = 1", cfg)
        self.assertIn("net.core.somaxconn = 4096", cfg)

    def test_audit_network_subsystem_structure(self):
        """Verify audit_network_subsystem returns expected dictionary keys."""
        res = audit_network_subsystem()
        self.assertIn("congestion_control", res)
        self.assertIn("default_qdisc", res)
        self.assertIn("tcp_fastopen", res)
        self.assertIn("slow_start_after_idle", res)
        self.assertIn("somaxconn", res)
        self.assertIn("tcp_max_syn_backlog", res)
        self.assertIn("tcp_tw_reuse", res)
        self.assertIn("tcp_fin_timeout", res)
        self.assertIn("tcp_notsent_lowat", res)
        self.assertIn("network_dropin_present", res)

    def test_audit_network_subsystem_mocked(self):
        """Verify audit_network_subsystem parsing with mocked sysctl reads."""
        with patch("os_manager.commands.tune._read_sysctl") as mock_read, \
             patch("pathlib.Path.is_file") as mock_is_file:
            def mock_sysctl(key: str) -> str:
                mapping = {
                    "net.ipv4.tcp_congestion_control": "bbr",
                    "net.core.default_qdisc": "fq_codel",
                    "net.ipv4.tcp_fastopen": "3",
                    "net.ipv4.tcp_slow_start_after_idle": "0",
                    "net.core.somaxconn": "8192",
                    "net.ipv4.tcp_max_syn_backlog": "8192",
                    "net.ipv4.tcp_tw_reuse": "1",
                    "net.ipv4.tcp_fin_timeout": "15",
                    "net.ipv4.tcp_notsent_lowat": "16384",
                }
                return mapping.get(key, "unknown")

            mock_read.side_effect = mock_sysctl
            mock_is_file.return_value = True

            res = audit_network_subsystem()
            self.assertEqual(res["congestion_control"], "bbr")
            self.assertEqual(res["default_qdisc"], "fq_codel")
            self.assertEqual(res["tcp_fastopen"], "3")
            self.assertEqual(res["slow_start_after_idle"], "0")
            self.assertEqual(res["somaxconn"], "8192")
            self.assertTrue(res["network_dropin_present"])


if __name__ == "__main__":
    unittest.main()
