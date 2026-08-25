"""Asynchronous Stdio Server Daemon for Model Context Protocol."""

import asyncio
import sys
from typing import Optional

from .protocol import (
    INTERNAL_ERROR,
    METHOD_NOT_FOUND,
    JsonRpcError,
    format_jsonrpc_response,
    parse_jsonrpc_message,
)
from .tools import execute_tool, get_tool_definitions


class McpServer:
    """Dispatches JSON-RPC 2.0 MCP requests to internal tool and resource engines."""

    def __init__(self, name: str = "os-manager", version: str = "1.0.0"):
        self.name = name
        self.version = version

    async def handle_message(self, raw_line: str) -> Optional[str]:
        """Process a single JSON-RPC message string and return serialized response."""
        try:
            req = parse_jsonrpc_message(raw_line)
        except JsonRpcError as err:
            return format_jsonrpc_response(error=err, msg_id=None)

        # JSON-RPC 2.0 Notifications: id is None, must not return a response
        if req.id is None:
            try:
                await self._dispatch_method(req.method, req.params)
            except Exception:
                pass
            return None

        try:
            result = await self._dispatch_method(req.method, req.params)
            return format_jsonrpc_response(result=result, msg_id=req.id)
        except JsonRpcError as err:
            return format_jsonrpc_response(error=err, msg_id=req.id)
        except Exception as exc:
            err = JsonRpcError(code=INTERNAL_ERROR, message=f"Internal error: {exc}")
            return format_jsonrpc_response(error=err, msg_id=req.id)

    async def _dispatch_method(self, method: str, params: dict) -> dict:
        """Route method name to corresponding MCP handler."""
        if method == "initialize":
            return {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                },
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
            }
        elif method == "tools/list":
            return {"tools": get_tool_definitions()}
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            return execute_tool(tool_name, tool_args)
        elif method == "resources/list":
            return {"resources": []}
        elif method == "ping":
            return {}
        else:
            raise JsonRpcError(code=METHOD_NOT_FOUND, message=f"Method not found: {method}")


async def run_stdio_server() -> None:
    """Run standard I/O streaming event loop for MCP server."""
    server = McpServer()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_running_loop()
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line_bytes = await reader.readline()
        if not line_bytes:
            break
        raw_line = line_bytes.decode("utf-8")
        res_str = await server.handle_message(raw_line)
        if res_str:
            sys.stdout.write(res_str)
            sys.stdout.flush()
