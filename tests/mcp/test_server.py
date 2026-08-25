"""Unit tests for asynchronous Stdio MCP Server message dispatch loop."""

import asyncio
import json
import unittest

from os_manager.mcp.server import McpServer


class TestMcpServer(unittest.IsolatedAsyncioTestCase):
    """Verify MCP server message routing and response generation."""

    async def asyncSetUp(self) -> None:
        self.server = McpServer()

    async def test_handle_initialize_request(self) -> None:
        req = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "test-client", "version": "1.0"},
            },
            "id": 1,
        }
        res_str = await self.server.handle_message(json.dumps(req))
        self.assertIsNotNone(res_str)
        data = json.loads(res_str)
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(data["result"]["serverInfo"]["name"], "os-manager")

    async def test_handle_tools_list_request(self) -> None:
        req = {"jsonrpc": "2.0", "method": "tools/list", "id": 2}
        res_str = await self.server.handle_message(json.dumps(req))
        data = json.loads(res_str)
        self.assertEqual(data["id"], 2)
        tools = data["result"]["tools"]
        self.assertTrue(any(t["name"] == "osm_safe_exec" for t in tools))

    async def test_handle_tools_call_request(self) -> None:
        req = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "osm_safe_exec",
                "arguments": {"command": "echo 'test-mcp-call'"},
            },
            "id": 3,
        }
        res_str = await self.server.handle_message(json.dumps(req))
        data = json.loads(res_str)
        self.assertEqual(data["id"], 3)
        self.assertIn("test-mcp-call", data["result"]["content"][0]["text"])

    async def test_handle_ping_request(self) -> None:
        req = {"jsonrpc": "2.0", "method": "ping", "id": 4}
        res_str = await self.server.handle_message(json.dumps(req))
        data = json.loads(res_str)
        self.assertEqual(data["id"], 4)
        self.assertEqual(data["result"], {})

    async def test_handle_notification_suppresses_response(self) -> None:
        req = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        res_str = await self.server.handle_message(json.dumps(req))
        self.assertIsNone(res_str)

        req_custom = {
            "jsonrpc": "2.0",
            "method": "custom_notify",
            "params": {"key": "val"},
        }
        res_str_custom = await self.server.handle_message(json.dumps(req_custom))
        self.assertIsNone(res_str_custom)


if __name__ == "__main__":
    unittest.main()
