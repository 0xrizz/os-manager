"""Unit tests for JSON-RPC 2.0 protocol parsing and MCP message formatting."""

import json
import unittest

from os_manager.mcp.protocol import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    JsonRpcError,
    JsonRpcRequest,
    format_jsonrpc_response,
    parse_jsonrpc_message,
)


class TestMcpProtocol(unittest.TestCase):
    """Verify JSON-RPC 2.0 framing and error codes."""

    def test_parse_valid_initialize_request(self) -> None:
        raw = '{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05"}, "id": 1}'
        req = parse_jsonrpc_message(raw)
        self.assertEqual(req.method, "initialize")
        self.assertEqual(req.id, 1)
        self.assertEqual(req.params.get("protocolVersion"), "2024-11-05")

    def test_parse_invalid_json_raises_jsonrpc_error(self) -> None:
        raw = '{"jsonrpc": "2.0", "method": "broken'
        with self.assertRaises(JsonRpcError) as ctx:
            parse_jsonrpc_message(raw)
        self.assertEqual(ctx.exception.code, PARSE_ERROR)

    def test_parse_non_jsonrpc_raises_invalid_request(self) -> None:
        raw = '{"method": "tools/list", "id": 2}'  # missing jsonrpc: 2.0
        with self.assertRaises(JsonRpcError) as ctx:
            parse_jsonrpc_message(raw)
        self.assertEqual(ctx.exception.code, INVALID_REQUEST)

    def test_format_success_response(self) -> None:
        res_str = format_jsonrpc_response(result={"tools": []}, msg_id=42)
        data = json.loads(res_str)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertEqual(data["id"], 42)
        self.assertEqual(data["result"], {"tools": []})
        self.assertNotIn("error", data)

    def test_format_error_response(self) -> None:
        err = JsonRpcError(code=METHOD_NOT_FOUND, message="Method unknown")
        res_str = format_jsonrpc_response(error=err, msg_id="req-1")
        data = json.loads(res_str)
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertEqual(data["id"], "req-1")
        self.assertEqual(data["error"]["code"], METHOD_NOT_FOUND)
        self.assertEqual(data["error"]["message"], "Method unknown")


if __name__ == "__main__":
    unittest.main()
