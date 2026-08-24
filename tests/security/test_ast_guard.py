"""Unit tests for Shell AST Semantic Parser and Security Invariant Gate."""

import unittest
from os_manager.config.schema import InvariantsConfig, OsmConfig
from os_manager.security.ast_guard import (
    ShellASTValidator,
    evaluate_payload,
)


class TestShellASTGuard(unittest.TestCase):
    """Test AST analysis against command obfuscation, redirection, and invariant violations."""

    def setUp(self) -> None:
        self.invariants = InvariantsConfig()
        self.validator = ShellASTValidator(self.invariants)

    def test_safe_read_commands(self) -> None:
        safe_cmds = [
            "git status",
            "ls -la",
            "df -h",
            "pytest tests/ -v",
            "cat README.md",
            "python3 -m py_compile script.py",
        ]
        for cmd in safe_cmds:
            with self.subTest(cmd=cmd):
                allowed, violations, sandbox = self.validator.analyze_command(cmd)
                self.assertTrue(allowed, f"Safe command was blocked: {cmd}")
                self.assertEqual(len(violations), 0)
                self.assertFalse(sandbox)

    def test_blocked_file_redirection_attacks(self) -> None:
        attack_cmds = [
            "cat malicious_content > /etc/passwd",
            "echo 'root::0:0:::' >> /etc/shadow",
            "echo bad | tee /etc/sudoers",
            "echo x > /mnt/c/Windows/system.ini",
        ]
        for cmd in attack_cmds:
            with self.subTest(cmd=cmd):
                allowed, violations, _ = self.validator.analyze_command(cmd)
                self.assertFalse(allowed, f"Redirection attack bypassed guard: {cmd}")
                self.assertTrue(
                    any(v.category == "Redirection" for v in violations),
                    f"Violation category mismatch for {cmd}: {violations}",
                )

    def test_blocked_destructive_root_deletion(self) -> None:
        root_deletes = [
            "rm -rf /",
            "rm -rf /*",
            "rm -rf ~",
            "rm -rf $HOME",
            "rm -rf /home/user/*",
        ]
        for cmd in root_deletes:
            with self.subTest(cmd=cmd):
                allowed, violations, _ = self.validator.analyze_command(cmd)
                self.assertFalse(allowed, f"Root deletion bypassed guard: {cmd}")

    def test_blocked_destructive_system_binaries(self) -> None:
        blocked_cmds = [
            "mkfs.ext4 /dev/sda1",
            "fdisk /dev/nvme0n1",
            "parted /dev/nvme0n1 rm 1",
            "dd if=/dev/zero of=/dev/sda bs=1M",
            "wsl.exe --unregister Debian",
            "wsl --shutdown",
        ]
        for cmd in blocked_cmds:
            with self.subTest(cmd=cmd):
                allowed, violations, _ = self.validator.analyze_command(cmd)
                self.assertFalse(allowed, f"Destructive binary bypassed guard: {cmd}")

    def test_dynamic_eval_obfuscation_detected(self) -> None:
        obfuscated_cmds = [
            "eval $(echo cm0gLXJmIC8= | base64 -d)",
            "eval 'rm -rf /'",
            "exec bash -c 'cat /etc/shadow'",
        ]
        for cmd in obfuscated_cmds:
            with self.subTest(cmd=cmd):
                allowed, violations, _ = self.validator.analyze_command(cmd)
                self.assertFalse(allowed, f"Obfuscated eval bypassed guard: {cmd}")

    def test_risky_deletion_recommends_sandbox(self) -> None:
        risky_cmds = [
            "rm -rf /tmp/build_dir",
            "rm -rf ./node_modules",
            "rm -rf dist/ build/",
        ]
        for cmd in risky_cmds:
            with self.subTest(cmd=cmd):
                allowed, violations, sandbox = self.validator.analyze_command(cmd)
                self.assertTrue(allowed)
                self.assertEqual(len(violations), 0)
                self.assertTrue(sandbox, f"Sandbox was not recommended for {cmd}")

    def test_evaluate_payload_edit_write(self) -> None:
        payload_blocked = {
            "tool_name": "Write",
            "tool_input": {"file_path": "/etc/shadow", "content": "bad"},
        }
        res = evaluate_payload(payload_blocked)
        self.assertFalse(res.allowed)
        self.assertEqual(res.exit_code, 2)

        payload_allowed = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "README.md", "new_string": "hi"},
        }
        res_ok = evaluate_payload(payload_allowed)
        self.assertTrue(res_ok.allowed)
        self.assertEqual(res_ok.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
