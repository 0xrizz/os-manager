"""tests/test_terminal_customization.py - Unit tests for Starship, FZF, Bash, and Tmux."""

import tempfile
import unittest
from pathlib import Path

from os_manager.commands.tune import (
    generate_bash_hooks_block,
    generate_starship_config,
    generate_tmux_config,
    inject_bashrc_hooks,
)


class TestTerminalCustomization(unittest.TestCase):
    """Unit tests for terminal developer experience tooling."""

    def test_generate_starship_config(self):
        """Verify Starship prompt TOML configuration contents."""
        cfg = generate_starship_config()
        self.assertIn("[directory]", cfg)
        self.assertIn("[git_branch]", cfg)
        self.assertIn("[cmd_duration]", cfg)
        self.assertIn("[python]", cfg)

    def test_generate_tmux_config(self):
        """Verify Tmux developer starter profile contents."""
        cfg = generate_tmux_config()
        self.assertIn("set -g mouse on", cfg)
        self.assertIn("xterm-256color", cfg)
        self.assertIn("setw -g mode-keys vi", cfg)

    def test_inject_bashrc_hooks_idempotency(self):
        """Verify bashrc hook injection is strictly idempotent."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("# Existing bashrc\nexport FOO=bar\n")
            f.flush()
            bashrc_path = f.name

        try:
            # First injection
            ok1 = inject_bashrc_hooks(bashrc_path=bashrc_path)
            self.assertTrue(ok1)
            content1 = Path(bashrc_path).read_text()
            self.assertIn("# --- os-manager Terminal Power-Up Hooks ---", content1)
            self.assertIn("alias ls=\"eza --icons\"", content1)

            # Second injection (must not duplicate)
            ok2 = inject_bashrc_hooks(bashrc_path=bashrc_path)
            self.assertTrue(ok2)
            content2 = Path(bashrc_path).read_text()
            self.assertEqual(content1.count("# --- os-manager Terminal Power-Up Hooks ---"), 1)
            self.assertEqual(content2.count("# --- os-manager Terminal Power-Up Hooks ---"), 1)
        finally:
            Path(bashrc_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
