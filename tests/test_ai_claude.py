"""tests/test_ai_claude.py - Unit tests for osm ai claude launcher."""

import unittest
from unittest.mock import MagicMock, patch

from os_manager.commands.ai import run_ai
from os_manager.commands.ai_claude import launch_claude


class TestAiClaudeLauncher(unittest.TestCase):
    """Test suite for on-demand Claude Code launcher."""

    @patch("subprocess.run")
    @patch("os_manager.commands.ai_claude.check_gateway_health")
    def test_launch_claude_when_online(self, mock_health, mock_run):
        """Verify launching claude when gateways are already healthy."""
        mock_health.return_value = {
            "headroom": {"online": True},
            "router": {"online": True},
        }
        mock_run.return_value.returncode = 0

        code = launch_claude(["--version"])
        self.assertEqual(code, 0)
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(kwargs["env"]["ANTHROPIC_BASE_URL"], "http://127.0.0.1:8787")

    @patch("subprocess.run")
    @patch("os_manager.commands.ai_claude.manage_services")
    @patch("os_manager.commands.ai_claude.check_gateway_health")
    def test_launch_claude_auto_start_when_offline(self, mock_health, mock_manage, mock_run):
        """Verify automatic startup when gateways are offline."""
        mock_health.side_effect = [
            {"headroom": {"online": False}, "router": {"online": False}},
            {"headroom": {"online": True}, "router": {"online": True}},
        ]
        mock_run.return_value.returncode = 0

        code = launch_claude([])
        self.assertEqual(code, 0)
        mock_manage.assert_called_once_with("start")

    @patch("shutil.which", return_value=None)
    @patch("os.path.exists", return_value=False)
    @patch("os_manager.commands.ai_claude.check_gateway_health")
    def test_launch_claude_binary_missing(self, mock_health, mock_exists, mock_which):
        """Verify graceful error when Claude binary is not found."""
        mock_health.return_value = {
            "headroom": {"online": True},
            "router": {"online": True},
        }
        code = launch_claude([])
        self.assertEqual(code, 1)

    @patch("subprocess.run", side_effect=OSError("Exec failed"))
    @patch("shutil.which", return_value="/usr/local/bin/claude")
    @patch("os_manager.commands.ai_claude.check_gateway_health")
    def test_launch_claude_execution_failure(self, mock_health, mock_which, mock_run):
        """Verify handling of subprocess execution exception."""
        mock_health.return_value = {
            "headroom": {"online": True},
            "router": {"online": True},
        }
        code = launch_claude(["--prompt", "hello"])
        self.assertEqual(code, 1)

    @patch("subprocess.run")
    @patch("os_manager.commands.ai_claude.manage_services")
    @patch("os_manager.commands.ai_claude.check_gateway_health")
    def test_launch_claude_headroom_remains_offline(self, mock_health, mock_manage, mock_run):
        """Verify warning when headroom is not online after retry loop."""
        mock_health.return_value = {
            "headroom": {"online": False},
            "router": {"online": False},
        }
        mock_run.return_value.returncode = 0
        with patch("time.sleep"):
            code = launch_claude(["--help"])
        self.assertEqual(code, 0)
        mock_manage.assert_called_once_with("start")

    @patch("os_manager.commands.ai_claude.launch_claude", return_value=0)
    def test_run_ai_claude_delegation(self, mock_launch):
        """Verify osm ai claude delegates to launch_claude with remaining args."""
        code = run_ai(["claude", "--model", "claude-3-7-sonnet"])
        self.assertEqual(code, 0)
        mock_launch.assert_called_once_with(["--model", "claude-3-7-sonnet"])
