"""Unit tests for multi-client MCP configuration installer."""

import json
from pathlib import Path
import tempfile
import unittest

from os_manager.mcp.client_config import (
    install_antigravity_mcp_config,
    install_claude_mcp_config,
    install_cursor_mcp_config,
)


class TestMcpClientConfig(unittest.TestCase):
    """Verify idempotent JSON configuration injection for AI coding tools."""

    def setUp(self) -> None:
        self.test_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.test_dir.name)

    def tearDown(self) -> None:
        self.test_dir.cleanup()

    def test_install_claude_mcp_config(self) -> None:
        claude_settings = self.root / "settings.json"
        claude_settings.write_text('{"permissions": {}}', encoding="utf-8")

        success = install_claude_mcp_config(target_file=claude_settings)
        self.assertTrue(success)

        data = json.loads(claude_settings.read_text(encoding="utf-8"))
        self.assertIn("mcpServers", data)
        self.assertIn("os-manager", data["mcpServers"])
        self.assertEqual(data["mcpServers"]["os-manager"]["command"], "osm")
        self.assertIn("serve", data["mcpServers"]["os-manager"]["args"])

    def test_install_cursor_mcp_config(self) -> None:
        cursor_mcp = self.root / "cursor_mcp.json"
        success = install_cursor_mcp_config(target_file=cursor_mcp)
        self.assertTrue(success)

        data = json.loads(cursor_mcp.read_text(encoding="utf-8"))
        self.assertIn("mcpServers", data)
        self.assertEqual(data["mcpServers"]["os-manager"]["command"], "osm")

    def test_install_antigravity_mcp_config(self) -> None:
        agy_mcp = self.root / "agy_mcp.json"
        success = install_antigravity_mcp_config(target_file=agy_mcp)
        self.assertTrue(success)

        data = json.loads(agy_mcp.read_text(encoding="utf-8"))
        self.assertIn("mcpServers", data)

    def test_run_mcp_cli_tools(self) -> None:
        from os_manager.commands.mcp import run_mcp
        code = run_mcp(["tools"])
        self.assertEqual(code, 0)

    def test_run_mcp_cli_install(self) -> None:
        from os_manager.commands.mcp import run_mcp
        code = run_mcp(["install", "--client", "claude"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
