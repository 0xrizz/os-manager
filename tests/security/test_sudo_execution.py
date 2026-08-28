"""Unit and integration tests for non-interactive sudo execution and AST security guard."""

import json
from pathlib import Path
import subprocess
import unittest

from os_manager.config.schema import InvariantsConfig
from os_manager.security.ast_guard import ShellASTValidator, evaluate_payload

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
SUDO_EXEC_SCRIPT = WORKSPACE_ROOT / "scripts" / "sudo_exec.sh"
HOOK_PATH = WORKSPACE_ROOT / "scripts" / "hooks" / "pre_tool_guard.sh"


class TestSudoExecutionASTGuard(unittest.TestCase):
    """Verify AST security guard catches bare interactive sudo while allowing non-interactive patterns."""

    def setUp(self) -> None:
        self.validator = ShellASTValidator(InvariantsConfig())

    def test_bare_sudo_commands_blocked(self) -> None:
        blocked_commands = [
            "sudo apt-get update",
            "sudo systemctl restart nginx",
            "sudo cp foo.txt /etc/foo.conf",
            "sudo sysctl -p",
            "sudo chown -R root:root /var/log",
            "echo 123; sudo apt install -y curl",
        ]
        for cmd in blocked_commands:
            with self.subTest(cmd=cmd):
                allowed, violations, _ = self.validator.analyze_command(cmd)
                self.assertFalse(allowed, f"Bare sudo command was unexpectedly allowed: {cmd}")
                self.assertTrue(
                    any("Interactive 'sudo' invocation detected" in v.reason for v in violations),
                    f"Expected interactive sudo reason in violations for: {cmd}",
                )

    def test_non_interactive_sudo_commands_allowed(self) -> None:
        allowed_commands = [
            "./scripts/sudo_exec.sh apt-get update",
            "scripts/sudo_exec.sh systemctl restart nginx",
            "echo '$PASS' | sudo -S apt-get update",
            "grep SUDO_PASSWORD .env | sudo -S systemctl restart foo",
            "sudo -S systemctl restart foo",
            "sudo -n true",
            "sudo -n systemctl is-active docker",
            "sudo -h",
            "sudo --version",
        ]
        for cmd in allowed_commands:
            with self.subTest(cmd=cmd):
                allowed, violations, _ = self.validator.analyze_command(cmd)
                self.assertTrue(allowed, f"Valid non-interactive command was blocked: {cmd}, violations: {violations}")

    def test_pre_tool_guard_blocks_bare_sudo_exit_code_2(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "sudo apt-get update"},
        }
        proc = subprocess.run(
            [str(HOOK_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Interactive 'sudo' invocation detected", proc.stderr)
        self.assertIn("./scripts/sudo_exec.sh", proc.stderr)

    def test_pre_tool_guard_allows_sudo_exec_wrapper(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "./scripts/sudo_exec.sh id"},
        }
        proc = subprocess.run(
            [str(HOOK_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)

    def test_sudo_exec_script_execution(self) -> None:
        """Verify sudo_exec.sh executes a simple non-destructive command."""
        self.assertTrue(SUDO_EXEC_SCRIPT.exists())
        self.assertTrue(SUDO_EXEC_SCRIPT.stat().st_mode & 0o111)

        proc = subprocess.run(
            [str(SUDO_EXEC_SCRIPT), "id", "-u"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "0")


if __name__ == "__main__":
    unittest.main()
