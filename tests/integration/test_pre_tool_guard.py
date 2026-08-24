"""Integration tests for pre_tool_guard.sh lifecycle hook."""

import json
from pathlib import Path
import subprocess
import unittest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = WORKSPACE_ROOT / "scripts" / "hooks" / "pre_tool_guard.sh"


class TestPreToolGuardHook(unittest.TestCase):
    """Verify pre_tool_guard.sh executes AST evaluation and enforces Exit 2 invariants."""

    def _run_hook(self, payload: dict) -> tuple[int, str, str]:
        proc = subprocess.run(
            [str(HOOK_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def test_allowed_bash_command(self) -> None:
        payload = {"tool_name": "Bash", "tool_input": {"command": "git status"}}
        rc, _, _ = self._run_hook(payload)
        self.assertEqual(rc, 0)

    def test_blocked_file_redirection_attack(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "cat evil > /etc/passwd"},
        }
        rc, _, stderr = self._run_hook(payload)
        self.assertEqual(rc, 2)
        self.assertIn("HARNESS SECURITY BLOCKED", stderr)

    def test_blocked_obfuscated_eval(self) -> None:
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "eval $(echo cm0gLXJmIC8= | base64 -d)"},
        }
        rc, _, stderr = self._run_hook(payload)
        self.assertEqual(rc, 2)
        self.assertIn("HARNESS SECURITY BLOCKED", stderr)

    def test_blocked_edit_host_windows_files(self) -> None:
        payload = {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "/mnt/c/Windows/System32/drivers/etc/hosts",
                "old_string": "a",
                "new_string": "b",
            },
        }
        rc, _, stderr = self._run_hook(payload)
        self.assertEqual(rc, 2)
        self.assertIn("Modification targeting protected system path is strictly forbidden", stderr)



if __name__ == "__main__":
    unittest.main()
