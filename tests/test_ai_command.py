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

    def test_is_port_in_use_true_and_false(self):
        """Verify is_port_in_use accurately checks socket binding."""
        from os_manager.commands.ai import is_port_in_use
        import socket

        # Test against a temporarily bound listening socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            s.listen(1)
            port = s.getsockname()[1]
            self.assertTrue(is_port_in_use(port))

        # Test against a port that is now closed
        self.assertFalse(is_port_in_use(port))

    @patch("shutil.which")
    @patch("os.path.isfile")
    @patch("os.access")
    def test_get_mise_cmd_with_mise_binary(self, mock_access, mock_isfile, mock_which):
        """Verify get_mise_cmd resolves mise executable when available."""
        from os_manager.commands.ai import get_mise_cmd

        mock_which.return_value = "/home/rizz/.local/bin/mise"
        mock_isfile.return_value = True
        mock_access.return_value = True

        cmd = get_mise_cmd("exec", "--", "9router", "--tray")
        self.assertEqual(cmd, ["/home/rizz/.local/bin/mise", "exec", "--", "9router", "--tray"])

    @patch("shutil.which", return_value=None)
    @patch("os.path.isfile", return_value=False)
    def test_get_mise_cmd_fallback_when_mise_missing(self, mock_isfile, mock_which):
        """Verify get_mise_cmd falls back to direct invocation when mise is absent."""
        from os_manager.commands.ai import get_mise_cmd

        cmd = get_mise_cmd("exec", "--", "9router")
        self.assertEqual(cmd, ["exec", "--", "9router"])

    @patch("subprocess.run")
    def test_find_gnome_9router_scopes(self, mock_run):
        """Verify discovery of active GNOME transient scopes for 9router."""
        from os_manager.commands.ai import find_gnome_9router_scopes

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="app-gnome-9router-2511.scope loaded active running 9router\n",
        )
        scopes = find_gnome_9router_scopes()
        self.assertEqual(scopes, ["app-gnome-9router-2511.scope"])

    @patch("subprocess.run")
    def test_find_9router_pids(self, mock_run):
        """Verify discovery of 9router PIDs via pgrep."""
        from os_manager.commands.ai import find_9router_pids

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="2511\n4096\n",
        )
        pids = find_9router_pids()
        self.assertEqual(pids, [2511, 4096])

    @patch("time.sleep")
    @patch("os_manager.commands.ai.is_port_in_use")
    @patch("os_manager.commands.ai.find_9router_pids")
    @patch("os_manager.commands.ai.find_gnome_9router_scopes")
    @patch("subprocess.run")
    def test_manage_services_stop_full_flow(
        self, mock_run, mock_scopes, mock_pids, mock_port, mock_sleep
    ):
        """Verify manage_services('stop') executes static units, scopes, and verifies drain."""
        from os_manager.commands.ai import manage_services

        mock_scopes.return_value = ["app-gnome-9router-2511.scope"]
        mock_pids.return_value = []
        # Port initially in use, then freed
        mock_port.side_effect = [True, False]
        mock_run.return_value = MagicMock(returncode=0)

        code = manage_services("stop")
        self.assertEqual(code, 0)

        # Verify GNOME scope was stopped
        mock_run.assert_any_call(["systemctl", "--user", "stop", "app-gnome-9router-2511.scope"], check=False)

    @patch("subprocess.run", side_effect=Exception("systemctl error"))
    def test_find_gnome_9router_scopes_exception(self, mock_run):
        """Verify find_gnome_9router_scopes returns empty list on exception."""
        from os_manager.commands.ai import find_gnome_9router_scopes

        self.assertEqual(find_gnome_9router_scopes(), [])

    @patch("subprocess.run", side_effect=Exception("pgrep error"))
    def test_find_9router_pids_exception(self, mock_run):
        """Verify find_9router_pids returns empty list on exception."""
        from os_manager.commands.ai import find_9router_pids

        self.assertEqual(find_9router_pids(), [])

    @patch("subprocess.run")
    @patch("os.getpid", return_value=1234)
    def test_find_9router_pids_filters_self(self, mock_getpid, mock_run):
        """Verify find_9router_pids filters out current process PID."""
        from os_manager.commands.ai import find_9router_pids

        mock_run.return_value = MagicMock(returncode=0, stdout="1234\n5678\n")
        self.assertEqual(find_9router_pids(), [5678])

    @patch("time.sleep")
    @patch("os.kill")
    @patch("os_manager.commands.ai.is_port_in_use")
    @patch("os_manager.commands.ai.find_9router_pids")
    @patch("os_manager.commands.ai.find_gnome_9router_scopes")
    @patch("subprocess.run")
    def test_stop_ai_services_pid_fallback_sigterm_and_sigkill(
        self, mock_run, mock_scopes, mock_pids, mock_port, mock_kill, mock_sleep
    ):
        """Verify stop_ai_services sends SIGTERM and escalates to SIGKILL if port remains bound."""
        import signal
        from os_manager.commands.ai import stop_ai_services

        mock_scopes.return_value = []
        mock_pids.return_value = [9999]
        # Port is in use for: initial check, check after SIGTERM, check during drain, then freed
        mock_port.side_effect = [True, True, False]
        mock_run.return_value = MagicMock(returncode=0)

        code = stop_ai_services()
        self.assertEqual(code, 0)
        mock_kill.assert_any_call(9999, signal.SIGTERM)
        mock_kill.assert_any_call(9999, signal.SIGKILL)

    @patch("time.time")
    @patch("time.sleep")
    @patch("os_manager.commands.ai.is_port_in_use", return_value=True)
    @patch("os_manager.commands.ai.find_9router_pids", return_value=[])
    @patch("os_manager.commands.ai.find_gnome_9router_scopes", return_value=[])
    @patch("subprocess.run")
    def test_stop_ai_services_drain_timeout(
        self, mock_run, mock_scopes, mock_pids, mock_port, mock_sleep, mock_time
    ):
        """Verify stop_ai_services returns 1 if port 20128 does not release within timeout."""
        from os_manager.commands.ai import stop_ai_services

        # Simulate time exceeding drain_deadline (start 100.0, then 104.0)
        mock_time.side_effect = [100.0, 104.0]
        code = stop_ai_services()
        self.assertEqual(code, 1)

    @patch("os_manager.commands.ai.check_gateway_health")
    @patch("os_manager.commands.ai.is_port_in_use", return_value=True)
    def test_start_ai_services_already_running(self, mock_port, mock_health):
        """Verify start_ai_services skips launch if 9router is already healthy."""
        from os_manager.commands.ai import start_ai_services

        mock_health.return_value = {
            "headroom": {"online": True},
            "router": {"online": True},
        }
        code = start_ai_services()
        self.assertEqual(code, 0)

    @patch("subprocess.run")
    @patch("os_manager.commands.ai.check_gateway_health")
    @patch("os_manager.commands.ai.is_port_in_use", return_value=False)
    @patch("os_manager.commands.ai.get_mise_cmd")
    def test_start_ai_services_launches_under_mise(self, mock_mise, mock_port, mock_health, mock_run):
        """Verify start_ai_services falls back to launching 9router via mise when unit is missing."""
        from os_manager.commands.ai import start_ai_services

        mock_mise.return_value = ["/home/rizz/.local/bin/mise", "exec", "--", "9router", "--tray", "--skip-update"]
        # systemctl start app-9router@autostart fails with code 1
        mock_run.side_effect = [
            MagicMock(returncode=1),  # systemctl start app-9router@autostart
            MagicMock(returncode=0),  # systemd-run --user --unit=app-9router ...
            MagicMock(returncode=0),  # systemctl start headroom-default
        ]
        mock_health.return_value = {
            "headroom": {"online": True},
            "router": {"online": True},
        }

        code = start_ai_services()
        self.assertEqual(code, 0)
        # Verify systemd-run was called with mise command
        mock_run.assert_any_call(
            ["systemd-run", "--user", "--unit=app-9router", "--", "/home/rizz/.local/bin/mise", "exec", "--", "9router", "--tray", "--skip-update"],
            check=False
        )

    @patch("os_manager.commands.ai.start_ai_services", return_value=0)
    @patch("os_manager.commands.ai.stop_ai_services", return_value=0)
    def test_manage_services_restart_calls_stop_then_start(self, mock_stop, mock_start):
        """Verify manage_services('restart') cleanly chains stop and start."""
        from os_manager.commands.ai import manage_services

        code = manage_services("restart")
        self.assertEqual(code, 0)
        mock_stop.assert_called_once()
        mock_start.assert_called_once()


