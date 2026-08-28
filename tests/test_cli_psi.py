"""tests/test_cli_psi.py - Unit tests for osm psi CLI command router."""

import io
import json
import unittest
from unittest.mock import MagicMock, patch

from os_manager.cli import main


class TestCliPsi(unittest.TestCase):
    """Test suite for osm psi CLI command dispatcher."""

    def test_osm_psi_status_json(self):
        """Test 'osm psi status --json' output."""
        mock_telemetry = {
            "supported": True,
            "daemon_active": True,
            "cpu": {"some_avg10": 0.5, "some_avg60": 0.2, "some_avg300": 0.1},
            "memory": {"some_avg10": 1.2, "full_avg10": 0.0},
            "io": {"some_avg10": 3.4, "full_avg10": 1.1},
            "zram_devices": ["/sys/block/zram0/compact"],
        }
        with patch("os_manager.commands.psi.audit_psi_telemetry", return_value=mock_telemetry), \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["psi", "status", "--json"])
            self.assertEqual(code, 0)
            data = json.loads(mock_out.getvalue())
            self.assertTrue(data["supported"])
            self.assertTrue(data["daemon_active"])

    def test_osm_psi_compact(self):
        """Test 'osm psi compact' manual trigger."""
        with patch("os_manager.commands.psi.compact_zram_devices", return_value=["/sys/block/zram0/compact"]) as mock_comp, \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["psi", "compact"])
            self.assertEqual(code, 0)
            mock_comp.assert_called_once()
            self.assertIn("Compacted 1 zRAM devices", mock_out.getvalue())

    def test_osm_psi_daemon_status(self):
        """Test 'osm psi daemon status'."""
        with patch("os_manager.commands.psi.manage_psi_daemon", return_value={"installed": True, "active": True, "enabled": True}) as mock_manage, \
             patch("sys.stdout", new_callable=io.StringIO) as mock_out:
            code = main(["psi", "daemon", "status"])
            self.assertEqual(code, 0)
            mock_manage.assert_called_once_with("status")
            self.assertIn("Active: True", mock_out.getvalue())
