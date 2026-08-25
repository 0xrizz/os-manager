"""Unit tests verifying agent definition schemas, decoupling, and portability."""

from pathlib import Path
import re
import unittest

FORBIDDEN_HARDCODED_PATTERNS = [
    re.compile(r"/dev/nvme0n1p4"),
    re.compile(r"81WD"),
    re.compile(r"ALC298.*strictly"),
]

REQUIRED_AGENTS = [
    "audio-hardware-tuner.md",
    "disaster-recovery-engineer.md",
    "linux-migration-engineer.md",
    "perf-optimizer.md",
    "prompt-architect.md",
    "security-auditor.md",
    "system-operator.md",
    "test-verifier.md",
    "tmux-agents-coordinator.md",
]


class TestAgentDefinitions(unittest.TestCase):
    """Validate agent definition structure, frontmatter, and open-source decoupling."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent
        self.claude_agents_dir = self.repo_root / ".claude" / "agents"
        self.agents_dir = self.repo_root / ".agents" / "agents"

    def test_all_required_agents_exist(self) -> None:
        for agent_file in REQUIRED_AGENTS:
            claude_path = self.claude_agents_dir / agent_file
            self.assertTrue(claude_path.is_file(), f"Missing Claude agent: {agent_file}")

    def test_no_hardcoded_personal_paths_in_claude_agents(self) -> None:
        for agent_file in REQUIRED_AGENTS:
            file_path = self.claude_agents_dir / agent_file
            content = file_path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_HARDCODED_PATTERNS:
                self.assertFalse(
                    pattern.search(content),
                    f"Forbidden personal constant '{pattern.pattern}' found in {agent_file}",
                )

    def test_claude_agents_frontmatter_validity(self) -> None:
        for agent_file in REQUIRED_AGENTS:
            file_path = self.claude_agents_dir / agent_file
            content = file_path.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---\n"), f"{agent_file} must start with YAML frontmatter")
            parts = content.split("---", 2)
            self.assertGreaterEqual(len(parts), 3, f"{agent_file} frontmatter closing missing")
            fm = parts[1]
            self.assertIn("name:", fm)
            self.assertIn("description:", fm)
            self.assertIn("tools:", fm)


if __name__ == "__main__":
    unittest.main()
