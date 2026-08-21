"""tests/test_upgrade_command.py - Unit tests for osm upgrade CLI command."""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch


class TestUpgradeCli(unittest.TestCase):
    """Unit test suite for osm upgrade CLI command group."""

    def run_cli(self, args: list[str]) -> tuple[int, str, str]:
        """Helper to invoke osm main CLI with captured streams."""
        from os_manager.cli import main

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        with patch.object(sys, "argv", ["osm"] + args):
            with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                try:
                    exit_code = main()
                except SystemExit as exc:
                    exit_code = exc.code if isinstance(exc.code, int) else 0

        return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()

    def test_upgrade_help(self):
        """Verify osm upgrade --help displays available subcommands."""
        code, out, _ = self.run_cli(["upgrade", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("check", out)
        self.assertIn("dry-run", out)
        self.assertIn("start", out)
        self.assertIn("verify", out)
        self.assertIn("rebuild-venv", out)

    @patch("subprocess.run")
    def test_upgrade_check_delegation(self, mock_run):
        """Verify osm upgrade check delegates to upgrade_debian_trixie.sh --check."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[PASS] Pre-Flight PASSED", stderr="")
        code, out, _ = self.run_cli(["upgrade", "check"])
        self.assertEqual(code, 0)
        mock_run.assert_called_once()
        cmd_args = mock_run.call_args[0][0]
        self.assertTrue(any("upgrade_debian_trixie.sh" in arg for arg in cmd_args))
        self.assertIn("--check", cmd_args)

    @patch("subprocess.run")
    def test_upgrade_dry_run_delegation(self, mock_run):
        """Verify osm upgrade dry-run delegates with --dry-run flag."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[PASS] Dry-run completed", stderr="")
        code, out, _ = self.run_cli(["upgrade", "dry-run"])
        self.assertEqual(code, 0)
        cmd_args = mock_run.call_args[0][0]
        self.assertIn("--dry-run", cmd_args)

    @patch("subprocess.run")
    def test_upgrade_verify_delegation(self, mock_run):
        """Verify osm upgrade verify delegates with --verify flag."""
        mock_run.return_value = MagicMock(returncode=0, stdout="[PASS] Hardware verified", stderr="")
        code, out, _ = self.run_cli(["upgrade", "verify"])
        self.assertEqual(code, 0)
        cmd_args = mock_run.call_args[0][0]
        self.assertIn("--verify", cmd_args)

    @patch("os_manager.commands.upgrade.rebuild_virtualenv")
    def test_upgrade_rebuild_venv_call(self, mock_rebuild):
        """Verify osm upgrade rebuild-venv calls venv rebuild helper."""
        mock_rebuild.return_value = 0
        code, out, _ = self.run_cli(["upgrade", "rebuild-venv"])
        self.assertEqual(code, 0)
        mock_rebuild.assert_called_once()

    @patch("shutil.which")
    @patch("subprocess.run")
    def test_upgrade_start_auto_tmux_launch(self, mock_run, mock_which):
        """Verify osm upgrade start launches in tmux if available."""
        mock_which.return_value = "/usr/bin/tmux"
        mock_run.return_value = MagicMock(returncode=0)

        with patch.dict(os.environ, {}, clear=True):
            code, out, _ = self.run_cli(["upgrade", "start", "--non-interactive"])
            self.assertEqual(code, 0)
            mock_run.assert_called_once()
            cmd_args = mock_run.call_args[0][0]
            self.assertEqual(cmd_args[0], "tmux")
            self.assertIn("osm-trixie-upgrade", cmd_args)


if __name__ == "__main__":
    unittest.main()
