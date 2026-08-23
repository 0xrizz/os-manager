"""tests/test_ai_command.py - Unit tests for osm ai command."""

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch

from os_manager.commands.ai import (
    check_gateway_health,
    get_telemetry_summary,
    open_dashboards,
    run_ai,
)


class TestAiCommand(unittest.TestCase):
    """Test suite for the osm ai command."""

    @patch("urllib.request.urlopen")
    def test_check_gateway_health_both_online(self, mock_urlopen):
        """Verify health check when both Headroom and 9Router are online."""
        mock_resp_headroom = MagicMock()
        mock_resp_headroom.status = 200
        mock_resp_headroom.read.return_value = b'{"status":"ok"}'

        mock_resp_9router = MagicMock()
        mock_resp_9router.status = 200
        mock_resp_9router.read.return_value = b'{"ok":true}'

        mock_urlopen.side_effect = [mock_resp_headroom, mock_resp_9router]

        health = check_gateway_health()
        self.assertTrue(health["headroom"]["online"])
        self.assertEqual(health["headroom"]["status_code"], 200)
        self.assertTrue(health["router"]["online"])
        self.assertEqual(health["router"]["status_code"], 200)

    @patch("urllib.request.urlopen")
    def test_check_gateway_health_offline(self, mock_urlopen):
        """Verify health check when gateways are unreachable."""
        mock_urlopen.side_effect = Exception("Connection refused")

        health = check_gateway_health()
        self.assertFalse(health["headroom"]["online"])
        self.assertFalse(health["router"]["online"])

    @patch("os.path.exists")
    @patch("builtins.open")
    def test_get_telemetry_summary(self, mock_open, mock_exists):
        """Verify telemetry extraction from proxy_savings.json."""
        mock_exists.return_value = True
        savings_data = {
            "lifetime": {
                "requests": 27,
                "tokens_saved": 16091,
                "compression_savings_usd": 0.048273,
            }
        }
        mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(savings_data)

        with patch("sqlite3.connect") as mock_sqlite:
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchall.return_value = [("Account 1", "antigravity")]
            mock_sqlite.return_value = mock_conn

            telemetry = get_telemetry_summary()
            self.assertEqual(telemetry["requests"], 27)
            self.assertEqual(telemetry["tokens_saved"], 16091)
            self.assertAlmostEqual(telemetry["savings_usd"], 0.048273)
            self.assertEqual(len(telemetry["active_providers"]), 1)

    @patch("webbrowser.open")
    def test_open_dashboards_both(self, mock_webbrowser):
        """Verify that open_dashboards opens both URLs."""
        code = open_dashboards(headroom=True, router=True)
        self.assertEqual(code, 0)
        self.assertEqual(mock_webbrowser.call_count, 2)
        mock_webbrowser.assert_any_call("http://127.0.0.1:8787/dashboard")
        mock_webbrowser.assert_any_call("http://127.0.0.1:20128/dashboard")

    @patch("urllib.request.urlopen")
    def test_run_ai_status_json(self, mock_urlopen):
        """Verify osm ai status --json outputs valid JSON."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status":"ok"}'
        mock_urlopen.return_value = mock_resp

        stdout = io.StringIO()
        with patch("os_manager.commands.ai.get_telemetry_summary", return_value={"requests": 10, "tokens_saved": 500, "savings_usd": 0.01, "active_providers": []}):
            with redirect_stdout(stdout):
                code = run_ai(["status", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(stdout.getvalue())
        self.assertIn("health", data)
        self.assertIn("telemetry", data)
