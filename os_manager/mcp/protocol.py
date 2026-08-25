"""JSON-RPC 2.0 Protocol Engine and MCP Frame Serializer."""

from dataclasses import dataclass, field
import json
from typing import Any, Dict, Optional

# Standard JSON-RPC 2.0 and MCP Error Codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


@dataclass
class JsonRpcError(Exception):
    code: int
    message: str
    data: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            out["data"] = self.data
        return out


@dataclass
class JsonRpcRequest:
    jsonrpc: str
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: Optional[Any] = None


def parse_jsonrpc_message(raw_line: str) -> JsonRpcRequest:
    """Parse raw JSON-RPC 2.0 request line."""
    if not raw_line or not raw_line.strip():
        raise JsonRpcError(code=INVALID_REQUEST, message="Empty request line")

    try:
        data = json.loads(raw_line.strip())
    except Exception as exc:
        raise JsonRpcError(code=PARSE_ERROR, message=f"Parse error: {exc}") from exc

    if not isinstance(data, dict):
        raise JsonRpcError(code=INVALID_REQUEST, message="Request must be a JSON object")

    if data.get("jsonrpc") != "2.0":
        raise JsonRpcError(code=INVALID_REQUEST, message="Missing or invalid 'jsonrpc' version (must be '2.0')")

    method = data.get("method")
    if not method or not isinstance(method, str):
        raise JsonRpcError(code=INVALID_REQUEST, message="Missing or invalid 'method' field")

    params = data.get("params", {})
    if not isinstance(params, dict):
        raise JsonRpcError(code=INVALID_PARAMS, message="'params' field must be a JSON object")

    msg_id = data.get("id")

    return JsonRpcRequest(
        jsonrpc="2.0",
        method=method,
        params=params,
        id=msg_id,
    )


def format_jsonrpc_response(
    result: Optional[Any] = None,
    error: Optional[JsonRpcError] = None,
    msg_id: Optional[Any] = None,
) -> str:
    """Format a single JSON-RPC 2.0 response line (newline terminated)."""
    payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": msg_id}

    if error is not None:
        payload["error"] = error.to_dict()
    else:
        payload["result"] = result if result is not None else {}

    return json.dumps(payload, separators=(",", ":")) + "\n"
