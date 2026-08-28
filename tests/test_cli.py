"""tests/test_cli.py - Unit tests for the osm Python CLI interface."""

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch


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

    @patch("os_manager.commands.tune_macos.run_macos_desktop_pipeline")
    def test_tune_desktop_preset_macos(self, mock_pipeline):
        """Verify osm tune desktop --preset macos executes successfully."""
        mock_pipeline.return_value = {"success": True, "snapshot": "/tmp/mock.dconf"}
        code, out, _ = self.run_cli(["tune", "desktop", "--preset", "macos"])
        self.assertEqual(code, 0)
        self.assertIn("macos", out.lower())

    def test_tune_terminal_audit(self):
        """Verify osm tune terminal audit runs."""
        code, out, _ = self.run_cli(["tune", "terminal", "audit"])
        self.assertEqual(code, 0)
        self.assertIn("Terminal environment audit", out)

    def test_cli_tune_storage_audit(self):
        """Verify osm tune storage --audit CLI invocation."""
        code, out, _ = self.run_cli(["tune", "storage", "--audit"])
        self.assertEqual(code, 0)
        self.assertIn("Storage", out)

    @patch("os_manager.commands.tune.migrate_ntfs_driver")
    @patch("subprocess.run")
    def test_cli_tune_storage_apply(self, mock_run, mock_migrate):
        """Verify osm tune storage --apply CLI invocation."""
        mock_migrate.return_value = {"success": True, "status": "migrated"}
        mock_run.return_value = MagicMock(returncode=0)
        code, out, _ = self.run_cli(["tune", "storage", "--apply"])
        self.assertEqual(code, 0)
        self.assertIn("Storage", out)

    def test_cli_tune_memory_audit(self):
        """Verify osm tune memory --audit CLI invocation."""
        code, out, _ = self.run_cli(["tune", "memory", "--audit"])
        self.assertEqual(code, 0)
        self.assertIn("EarlyOOM", out)

    @patch("subprocess.run")
    @patch("os_manager.commands.tune.configure_earlyoom", return_value=True)
    def test_cli_tune_memory_apply(self, mock_conf, mock_run):
        """Verify osm tune memory --apply CLI invocation."""
        mock_run.return_value = MagicMock(returncode=0)
        code, out, _ = self.run_cli(["tune", "memory", "--apply"])
        self.assertEqual(code, 0)
        self.assertIn("EarlyOOM", out)

    def test_cli_tune_hardware_audit(self):
        """Verify osm tune hardware --audit CLI invocation."""
        code, out, _ = self.run_cli(["tune", "hardware", "--audit"])
        self.assertEqual(code, 0)
        self.assertIn("Battery Conservation", out)

    @patch("os_manager.commands.tune.set_battery_conservation_mode", return_value=True)
    @patch("os_manager.commands.tune.set_fn_lock_mode", return_value=True)
    @patch("subprocess.run")
    def test_cli_tune_hardware_apply(self, mock_run, mock_fn, mock_bat):
        """Verify osm tune hardware --apply CLI invocation."""
        mock_run.return_value = MagicMock(returncode=0)
        code, out, _ = self.run_cli(["tune", "hardware", "--apply"])
        self.assertEqual(code, 0)
        self.assertIn("Hardware", out)

    def test_cli_tune_system_audit(self):
        """Verify osm tune system --audit CLI invocation."""
        code, out, _ = self.run_cli(["tune", "system", "--audit"])
        self.assertEqual(code, 0)
        self.assertIn("vm.swappiness", out)

    @patch("subprocess.run")
    def test_cli_tune_system_apply(self, mock_run):
        """Verify osm tune system --apply CLI invocation."""
        mock_run.return_value = MagicMock(returncode=0)
        code, out, _ = self.run_cli(["tune", "system", "--apply"])
        self.assertEqual(code, 0)

    def test_cli_tune_persist_status(self):
        """Verify osm tune persist --status CLI invocation."""
        code, out, _ = self.run_cli(["tune", "persist", "--status"])
        self.assertEqual(code, 0)
        self.assertIn("Persistence", out)

    @patch("os_manager.commands.tune.configure_hardware_persistence", return_value=True)
    def test_cli_tune_persist_enable(self, mock_persist):
        """Verify osm tune persist --enable CLI invocation."""
        code, out, _ = self.run_cli(["tune", "persist", "--enable"])
        self.assertEqual(code, 0)
        self.assertIn("Persistence", out)

    @patch("os_manager.commands.tune.configure_hardware_persistence", return_value=True)
    def test_cli_tune_persist_disable(self, mock_persist):
        """Verify osm tune persist --disable CLI invocation."""
        code, out, _ = self.run_cli(["tune", "persist", "--disable"])
        self.assertEqual(code, 0)
        self.assertIn("Persistence", out)

    def test_cli_tune_all_json(self):
        """Verify osm tune all --json output returns valid telemetry payload."""
        code, out, _ = self.run_cli(["tune", "all", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("subsystems", data)
        self.assertIn("storage", data["subsystems"])
        self.assertIn("memory", data["subsystems"])
        self.assertIn("hardware", data["subsystems"])
        self.assertIn("sysctl", data["subsystems"])
        self.assertEqual(data["status"], "success")

    def test_collect_tune_telemetry(self):
        """Verify collect_tune_telemetry produces valid dictionary adhering to schema."""
        from os_manager.commands.tune import collect_tune_telemetry
        telemetry = collect_tune_telemetry()
        self.assertEqual(telemetry["status"], "success")
        self.assertIn("timestamp", telemetry)
        self.assertIn("storage", telemetry["subsystems"])
        self.assertIn("memory", telemetry["subsystems"])
        self.assertIn("hardware", telemetry["subsystems"])
        self.assertIn("sysctl", telemetry["subsystems"])

    def test_cli_hsi_subcommand(self):
        """Verify that osm hsi routes to run_hsi."""
        with patch("os_manager.commands.hsi.run_hsi", return_value=0) as mock_hsi:
            from os_manager.cli import main
            code = main(["hsi", "audit"])
            self.assertEqual(code, 0)
            mock_hsi.assert_called_once_with(["audit"])

    def test_ai_command_help(self):
        """Verify osm ai --help displays available AI actions."""
        code, out, _ = self.run_cli(["ai", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("status", out)
        self.assertIn("dashboard", out)
        self.assertIn("start", out)

    @patch("os_manager.commands.ai.run_ai")
    def test_ai_command_dispatch(self, mock_run_ai):
        """Verify osm ai routes properly to run_ai dispatcher."""
        mock_run_ai.return_value = 0
        code, _, _ = self.run_cli(["ai", "status"])
        self.assertEqual(code, 0)
        mock_run_ai.assert_called_once_with(["status"])

    @patch("os_manager.commands.mcp.run_mcp")
    def test_mcp_command_dispatch(self, mock_run_mcp):
        """Verify osm mcp routes properly to run_mcp dispatcher."""
        mock_run_mcp.return_value = 0
        code, _, _ = self.run_cli(["mcp", "tools"])
        self.assertEqual(code, 0)
        mock_run_mcp.assert_called_once_with(["tools"])


    def test_cli_tune_revert_list(self):
        """Verify osm tune revert --list displays snapshots."""
        code, out, _ = self.run_cli(["tune", "revert", "--list"])
        self.assertEqual(code, 0)
        self.assertIn("Snapshots", out)

    def test_cli_tune_revert_dry_run(self):
        """Verify osm tune revert --dry-run simulates rollback."""
        code, out, _ = self.run_cli(["tune", "revert", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("PLAN", out)

    @patch("os_manager.commands.tune.revert_system_snapshot")
    def test_cli_tune_revert_apply(self, mock_revert):
        """Verify osm tune revert --id restores snapshot."""
        mock_revert.return_value = {"success": True, "snapshot_id": "snap_123", "restored_files": ["/etc/fstab"]}
        code, out, _ = self.run_cli(["tune", "revert", "--id", "snap_123"])
        self.assertEqual(code, 0)
        self.assertIn("Reverted", out)
        mock_revert.assert_called_once_with(snapshot_id="snap_123")

    def test_cli_tune_power_audit(self):
        """Verify osm tune power --audit executes."""
        code, out, _ = self.run_cli(["tune", "power", "--audit"])
        self.assertEqual(code, 0)
        self.assertIn("Power", out)

    def test_cli_perf_all_json(self):
        """Verify osm perf all --quick --json returns JSON metrics."""
        code, out, _ = self.run_cli(["perf", "all", "--quick", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("benchmarks", data)

    def test_cli_tune_scheduler_audit(self):
        """Verify osm tune scheduler --audit CLI invocation."""
        code, out, _ = self.run_cli(["tune", "scheduler", "--audit"])
        self.assertEqual(code, 0)
        self.assertIn("EEVDF", out)

    @patch("subprocess.run")
    def test_cli_tune_scheduler_apply(self, mock_run):
        """Verify osm tune scheduler --apply CLI invocation."""
        mock_run.return_value = MagicMock(returncode=0)
        code, out, _ = self.run_cli(["tune", "scheduler", "--apply"])
        self.assertEqual(code, 0)
        self.assertIn("EEVDF", out)

    def test_cli_tune_audio_audit(self):
        """Verify osm tune audio --audit CLI invocation."""
        code, out, _ = self.run_cli(["tune", "audio", "--audit"])
        self.assertEqual(code, 0)
        self.assertIn("PipeWire", out)

    @patch("subprocess.run")
    def test_cli_tune_audio_apply(self, mock_run):
        """Verify osm tune audio --apply CLI invocation."""
        mock_run.return_value = MagicMock(returncode=0)
        code, out, _ = self.run_cli(["tune", "audio", "--apply"])
        self.assertEqual(code, 0)
        self.assertIn("PipeWire", out)

    def test_cli_tune_all_dry_run(self):
        """Verify osm tune all --dry-run outputs plan simulation."""
        code, out, _ = self.run_cli(["tune", "all", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("PLAN", out)

    def test_cli_tune_storage_dry_run(self):
        """Verify osm tune storage --dry-run outputs plan simulation."""
        code, out, _ = self.run_cli(["tune", "storage", "--apply", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("PLAN", out)

    def test_cli_tune_memory_dry_run(self):
        """Verify osm tune memory --dry-run outputs plan simulation."""
        code, out, _ = self.run_cli(["tune", "memory", "--apply", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("PLAN", out)

    def test_cli_tune_scheduler_dry_run(self):
        """Verify osm tune scheduler --dry-run outputs plan simulation."""
        code, out, _ = self.run_cli(["tune", "scheduler", "--apply", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("PLAN", out)

    def test_cli_tune_audio_dry_run(self):
        """Verify osm tune audio --dry-run outputs plan simulation."""
        code, out, _ = self.run_cli(["tune", "audio", "--apply", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("PLAN", out)

    def test_cli_tune_power_dry_run(self):
        """Verify osm tune power --dry-run outputs plan simulation."""
        code, out, _ = self.run_cli(["tune", "power", "--apply", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("PLAN", out)

    def test_cli_tune_persist_dry_run(self):
        """Verify osm tune persist --dry-run outputs plan simulation."""
        code, out, _ = self.run_cli(["tune", "persist", "--enable", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("PLAN", out)

    def test_cli_tune_memory_remediate_zram_dry_run(self):
        """Verify osm tune memory --remediate-zram --dry-run CLI invocation."""
        code, out, _ = self.run_cli(["tune", "memory", "--remediate-zram", "--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("zRAM", out)

    def test_cli_tune_memory_remediate_zram_apply(self):
        """Verify osm tune memory --remediate-zram CLI invocation."""
        with patch("os_manager.commands.tune.remediate_zram_conflicts") as mock_rem:
            mock_rem.return_value = {
                "success": True,
                "dry_run": False,
                "actions": ["systemctl mask zramswap.service"],
                "initial_status": "CONFLICT_DETECTED",
                "post_status": "OPTIMAL",
                "message": "Remediation executed successfully.",
            }
            code, out, _ = self.run_cli(["tune", "memory", "--remediate-zram"])
            self.assertEqual(code, 0)
            self.assertIn("Remediation", out)
            mock_rem.assert_called_once_with(dry_run=False)

    def test_cli_tune_memory_remediate_zram_json(self):
        """Verify osm tune memory --remediate-zram --json CLI invocation."""
        with patch("os_manager.commands.tune.remediate_zram_conflicts") as mock_rem:
            mock_rem.return_value = {
                "success": True,
                "dry_run": True,
                "actions": ["systemctl mask zramswap.service"],
                "initial_status": "CONFLICT_DETECTED",
                "message": "Dry-run simulation completed.",
            }
            code, out, _ = self.run_cli(["tune", "memory", "--remediate-zram", "--dry-run", "--json"])
            self.assertEqual(code, 0)
            data = json.loads(out)
            self.assertTrue(data["success"])
            self.assertTrue(data["dry_run"])


if __name__ == "__main__":
    unittest.main()


