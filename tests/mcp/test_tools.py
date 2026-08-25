"""Unit tests for MCP tool declarations and execution handlers."""

import unittest
from os_manager.mcp.tools import execute_tool, get_tool_definitions


class TestMcpTools(unittest.TestCase):
    """Verify tool schemas and execution safety gates."""

    def test_get_tool_definitions_contains_core_tools(self) -> None:
        tools = get_tool_definitions()
        tool_names = [t["name"] for t in tools]
        self.assertIn("osm_safe_exec", tool_names)
        self.assertIn("osm_system_health", tool_names)
        self.assertIn("osm_sandbox_run", tool_names)
        self.assertIn("osm_tune", tool_names)

    def test_osm_safe_exec_allows_read_only_command(self) -> None:
        res = execute_tool("osm_safe_exec", {"command": "echo 'safe output'"})
        self.assertFalse(res.get("isError", False))
        content = res["content"][0]["text"]
        self.assertIn("safe output", content)

    def test_osm_safe_exec_blocks_destructive_redirection(self) -> None:
        res = execute_tool("osm_safe_exec", {"command": "cat /tmp/test > /etc/shadow"})
        self.assertTrue(res.get("isError", False))
        content = res["content"][0]["text"]
        self.assertIn("HARNESS SECURITY BLOCKED", content)

    def test_osm_system_health_returns_platform_metrics(self) -> None:
        res = execute_tool("osm_system_health", {})
        self.assertFalse(res.get("isError", False))
        content = res["content"][0]["text"]
        self.assertIn("platform", content)
        self.assertIn("cpu_count", content)

    def test_execute_unknown_tool_raises_error(self) -> None:
        res = execute_tool("nonexistent_tool", {})
        self.assertTrue(res.get("isError", False))
        self.assertIn("Unknown tool", res["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
