"""tests/test_cli.py - Unit tests for the osm Python CLI interface."""

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch


class TestOsmCli(unittest.TestCase):
    """Unit test cases for the os_manager CLI entrypoint."""

    def run_cli(self, args):
        """Execute CLI main function with captured stdout, stderr, and exit code."""
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

    def test_cli_help(self):
        """Verify --help flag prints usage information and returns 0."""
        code, out, _ = self.run_cli(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("usage: osm", out.lower())
        self.assertIn("check", out)
        self.assertIn("diag", out)

    def test_cli_version(self):
        """Verify --version flag displays package version."""
        code, out, _ = self.run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("1.0.0", out)

    def test_diag_command_text(self):
        """Verify osm diag outputs diagnostic details."""
        code, out, _ = self.run_cli(["diag"])
        self.assertEqual(code, 0)
        self.assertIn("OS-Manager Diagnostic Report", out)

    def test_diag_command_json(self):
        """Verify osm diag --json outputs valid parseable JSON."""
        code, out, _ = self.run_cli(["diag", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("platform", data)
        self.assertIn("cpu_count", data)

    def test_clean_command_dry_run(self):
        """Verify osm clean --dry-run executes safely."""
        code, out, _ = self.run_cli(["clean", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("Clean", out)

    def test_perf_command_quick(self):
        """Verify osm perf --quick completes with metrics."""
        code, out, _ = self.run_cli(["perf", "--quick"])
        self.assertEqual(code, 0)
        self.assertIn("Performance", out)

    def test_service_status_command(self):
        """Verify osm service status executes."""
        code, out, _ = self.run_cli(["service", "status"])
        self.assertEqual(code, 0)
        self.assertIn("Service", out)

    def test_init_command_dry_run(self):
        """Verify osm init --dry-run validates paths."""
        code, out, _ = self.run_cli(["init", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("Init", out)

    def test_tune_command_help(self):
        """Verify osm tune prints help and returns 0."""
        code, out, _ = self.run_cli(["tune"])
        self.assertEqual(code, 0)
        self.assertIn("usage: osm tune", out.lower())

    def test_tune_command_audit(self):
        """Verify osm tune audit outputs diagnostics."""
        code, out, _ = self.run_cli(["tune", "audit"])
        self.assertEqual(code, 0)
        self.assertIn("Debian 13 Hardware & Desktop Diagnostics", out)

    def test_tune_battery_status(self):
        """Verify osm tune battery status runs."""
        code, out, _ = self.run_cli(["tune", "battery", "status"])
        self.assertEqual(code, 0)
        self.assertIn("Battery Conservation Mode", out)

    def test_tune_profile_status(self):
        """Verify osm tune profile status runs."""
        code, out, _ = self.run_cli(["tune", "profile", "status"])
        self.assertEqual(code, 0)
        self.assertIn("Platform Profile", out)

    def test_tune_fn_lock_status(self):
        """Verify osm tune fn-lock status runs."""
        code, out, _ = self.run_cli(["tune", "fn-lock", "status"])
        self.assertEqual(code, 0)
        self.assertIn("Fn-Lock", out)

    def test_tune_gpu_status(self):
        """Verify osm tune gpu status runs."""
        code, out, _ = self.run_cli(["tune", "gpu", "status"])
        self.assertEqual(code, 0)
        self.assertIn("NVIDIA GPU", out)

    def test_tune_desktop_audit(self):
        """Verify osm tune desktop audit runs."""
        code, out, _ = self.run_cli(["tune", "desktop", "audit"])
        self.assertEqual(code, 0)
        self.assertIn("GTK Bookmarks", out)

    def test_tune_desktop_preset_macos(self):
        """Verify osm tune desktop --preset macos executes successfully."""
        code, out, _ = self.run_cli(["tune", "desktop", "--preset", "macos"])
        self.assertEqual(code, 0)
        self.assertIn("macos", out.lower())

    def test_tune_terminal_audit(self):
        """Verify osm tune terminal audit runs."""
        code, out, _ = self.run_cli(["tune", "terminal", "audit"])
        self.assertEqual(code, 0)
        self.assertIn("Terminal environment audit", out)


if __name__ == "__main__":
    unittest.main()
