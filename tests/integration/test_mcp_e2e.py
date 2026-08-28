"""End-to-End integration tests for `osm mcp serve` over stdio pipe."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


class TestMcpEndToEnd(unittest.TestCase):
    """Test full MCP handshake and tool invocation over subprocess stdio pipe."""

    def test_mcp_stdio_handshake_and_tool_call(self) -> None:
        venv_py = WORKSPACE_ROOT / ".venv/bin/python"
        py_bin = str(venv_py) if venv_py.is_file() else sys.executable
        proc = subprocess.Popen(
            [py_bin, "-m", "os_manager.cli", "mcp", "serve"],
            cwd=WORKSPACE_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # 1. Send initialize
        init_req = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
            "id": 1,
        }
        proc.stdin.write(json.dumps(init_req) + "\n")
        proc.stdin.flush()

        init_resp = json.loads(proc.stdout.readline())
        self.assertEqual(init_resp["id"], 1)
        self.assertEqual(init_resp["result"]["serverInfo"]["name"], "os-manager")

        # 2. Call osm_safe_exec
        tool_req = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "osm_safe_exec",
                "arguments": {"command": "echo 'e2e-mcp-verified'"},
            },
            "id": 2,
        }
        proc.stdin.write(json.dumps(tool_req) + "\n")
        proc.stdin.flush()

        tool_resp = json.loads(proc.stdout.readline())
        self.assertEqual(tool_resp["id"], 2)
        self.assertIn("e2e-mcp-verified", tool_resp["result"]["content"][0]["text"])

        # Terminate server
        proc.stdin.close()
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            proc.stderr.close()
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
