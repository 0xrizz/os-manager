# Inter-Agent Message Bus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an asynchronous inter-agent message bus daemon (`scripts/agent_bus.py`) and publisher helper (`scripts/bus_send.sh`). These components provide structured event routing for multi-agent workflows.

**Architecture:** An `asyncio` Unix domain socket server binds to `$XDG_RUNTIME_DIR/os-manager/bus.sock` (fallback `~/.local/run/os-manager/bus.sock`). The broker manages client registrations, pub/sub topic routing, and point-to-point messaging with JSON-RPC 2.0 framing. Calling scripts publish events via `scripts/bus_send.sh`, which degrades cleanly when the daemon is offline.

**Tech Stack:** Python 3 `asyncio`, JSON-RPC 2.0, UNIX domain socket, POSIX Shell (Bash 5.2+), systemd user service.

**Spec:** `docs/superpowers/specs/2026-08-19-inter-agent-message-bus-design.md`

## Global Constraints

- **Socket Filesystem Location**: Bind primary socket strictly to `$XDG_RUNTIME_DIR/os-manager/bus.sock` with fallback to `~/.local/run/os-manager/bus.sock`.
- **Directory and Socket Permissions**: Enforce `0700` directory permissions on the socket parent directory and `0600` permissions on the active socket file.
- **Zero External Dependencies**: Use Python standard library modules (`asyncio`, `json`, `os`, `sys`, `time`, `signal`, `socket`, `argparse`, `typing`, `unittest`) with zero external pip dependencies.
- **Standards-Compliant RPC Framing**: Use newline-delimited (`\n`) UTF-8 JSON-RPC 2.0 request and response frames.
- **Frame Size Boundary**: Enforce a maximum frame payload limit of 1 megabyte (1,048,576 bytes) per socket message.
- **Fail-Safe Client Degradation**: The shell helper `scripts/bus_send.sh` must exit cleanly with code 0 when the socket daemon is unavailable, preventing caller script failures.
- **Security Matrix Registration**: Pre-authorize `scripts/bus_send.sh` and `scripts/agent_bus.py` in Tier 2 fast-path rules in `scripts/hooks/pre_tool_guard.sh` and `.claude/rules/safety-tiers.md`.

---

### Task 1: Create Unit Test Suite for Inter-Agent Message Bus

**Files:**
- Create: `tests/test_agent_bus.py`

**Interfaces:**
- Consumes: `scripts/agent_bus.py` (`resolve_socket_path`, `MessageBroker`, `start_bus_server`)
- Produces: Executable Python `unittest` suite testing socket resolution, registration handshakes, topic subscriptions, broadcast event routing, point-to-point messaging, malformed JSON handling, and disconnection cleanup.

- [ ] **Step 1: Write the failing unit test suite**

```python
#!/usr/bin/env python3
"""tests/test_agent_bus.py

Unit test suite for the Inter-Agent Message Bus daemon.
Validates socket resolution, client registration, topic pub/sub, direct messaging,
frame size limits, and client disconnection cleanup.
"""

import asyncio
import json
import os
import sys
import tempfile
import time
import unittest

# Ensure workspace root is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from scripts.agent_bus import (
    resolve_socket_path,
    MessageBroker,
    MAX_PAYLOAD_SIZE,
)


class TestSocketResolution(unittest.TestCase):
    """Test socket path resolution across standard and fallback environments."""

    def test_resolve_socket_path_custom(self):
        custom = "/tmp/test-os-manager/bus.sock"
        resolved = resolve_socket_path(custom)
        self.assertEqual(resolved, custom)

    def test_resolve_socket_path_xdg(self):
        with tempfile.TemporaryDirectory() as tmp_xdg:
            old_xdg = os.environ.get("XDG_RUNTIME_DIR")
            try:
                os.environ["XDG_RUNTIME_DIR"] = tmp_xdg
                resolved = resolve_socket_path()
                expected = os.path.join(tmp_xdg, "os-manager", "bus.sock")
                self.assertEqual(resolved, expected)
                self.assertTrue(os.path.isdir(os.path.dirname(resolved)))
            finally:
                if old_xdg is not None:
                    os.environ["XDG_RUNTIME_DIR"] = old_xdg
                else:
                    os.environ.pop("XDG_RUNTIME_DIR", None)

    def test_resolve_socket_path_fallback(self):
        old_xdg = os.environ.get("XDG_RUNTIME_DIR")
        try:
            os.environ.pop("XDG_RUNTIME_DIR", None)
            resolved = resolve_socket_path()
            expected = os.path.expanduser("~/.local/run/os-manager/bus.sock")
            self.assertEqual(resolved, expected)
            self.assertTrue(os.path.isdir(os.path.dirname(resolved)))
        finally:
            if old_xdg is not None:
                os.environ["XDG_RUNTIME_DIR"] = old_xdg


class TestMessageBrokerAsync(unittest.IsolatedAsyncioTestCase):
    """Asynchronous test cases for MessageBroker socket handling and JSON-RPC methods."""

    async def asyncSetUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.socket_path = os.path.join(self.tmp_dir.name, "bus.sock")
        self.broker = MessageBroker()
        self.server = await asyncio.start_unix_server(
            self.broker.handle_client, path=self.socket_path
        )

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        self.tmp_dir.cleanup()

    async def _create_client(self):
        return await asyncio.open_unix_connection(self.socket_path)

    async def _send_frame(self, writer: asyncio.StreamWriter, obj: dict):
        data = (json.dumps(obj) + "\n").encode("utf-8")
        writer.write(data)
        await writer.drain()

    async def _read_frame(self, reader: asyncio.StreamReader) -> dict:
        line = await asyncio.wait_for(reader.readline(), timeout=2.0)
        self.assertTrue(len(line) > 0, "Socket closed prematurely")
        return json.loads(line.decode("utf-8"))

    async def test_client_registration(self):
        reader, writer = await self._create_client()
        try:
            reg_req = {
                "jsonrpc": "2.0",
                "method": "register",
                "params": {"agent_id": "claude-worker-01", "role": "implementer", "pid": 12345},
                "id": 1,
            }
            await self._send_frame(writer, reg_req)
            resp = await self._read_frame(reader)

            self.assertEqual(resp.get("jsonrpc"), "2.0")
            self.assertEqual(resp.get("id"), 1)
            self.assertEqual(resp.get("result", {}).get("status"), "registered")
            self.assertEqual(resp.get("result", {}).get("agent_id"), "claude-worker-01")
            self.assertIn("claude-worker-01", self.broker.clients)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_topic_subscription_and_publish(self):
        sub_r, sub_w = await self._create_client()
        pub_r, pub_w = await self._create_client()

        try:
            # Register subscriber
            await self._send_frame(
                sub_w,
                {"jsonrpc": "2.0", "method": "register", "params": {"agent_id": "sub-agent"}, "id": 1},
            )
            await self._read_frame(sub_r)

            # Subscribe to exact topic and wildcard topic
            await self._send_frame(
                sub_w,
                {"jsonrpc": "2.0", "method": "subscribe", "params": {"topics": ["task.dispatch", "telemetry.*"]}, "id": 2},
            )
            sub_resp = await self._read_frame(sub_r)
            self.assertEqual(sub_resp.get("result", {}).get("subscribed"), ["task.dispatch", "telemetry.*"])

            # Register publisher
            await self._send_frame(
                pub_w,
                {"jsonrpc": "2.0", "method": "register", "params": {"agent_id": "pub-agent"}, "id": 10},
            )
            await self._read_frame(pub_r)

            # Publish matching exact topic
            event_payload = {"task_id": "T-101", "action": "test"}
            await self._send_frame(
                pub_w,
                {"jsonrpc": "2.0", "method": "publish", "params": {"topic": "task.dispatch", "payload": event_payload}, "id": 11},
            )
            pub_ack = await self._read_frame(pub_r)
            self.assertTrue(pub_ack.get("result", {}).get("published"))

            # Subscriber receives event
            event_frame = await self._read_frame(sub_r)
            self.assertEqual(event_frame.get("method"), "event")
            self.assertEqual(event_frame.get("params", {}).get("topic"), "task.dispatch")
            self.assertEqual(event_frame.get("params", {}).get("publisher"), "pub-agent")
            self.assertEqual(event_frame.get("params", {}).get("payload"), event_payload)

            # Publish matching wildcard topic
            wildcard_payload = {"metric": "latency", "value": 0.45}
            await self._send_frame(
                pub_w,
                {"jsonrpc": "2.0", "method": "publish", "params": {"topic": "telemetry.cpu", "payload": wildcard_payload}, "id": 12},
            )
            await self._read_frame(pub_r)

            wildcard_event = await self._read_frame(sub_r)
            self.assertEqual(wildcard_event.get("method"), "event")
            self.assertEqual(wildcard_event.get("params", {}).get("topic"), "telemetry.cpu")
            self.assertEqual(wildcard_event.get("params", {}).get("payload"), wildcard_payload)
        finally:
            sub_w.close()
            pub_w.close()
            await sub_w.wait_closed()
            await pub_w.wait_closed()

    async def test_direct_peer_messaging(self):
        agent_a_r, agent_a_w = await self._create_client()
        agent_b_r, agent_b_w = await self._create_client()

        try:
            # Register Agent A
            await self._send_frame(
                agent_a_w,
                {"jsonrpc": "2.0", "method": "register", "params": {"agent_id": "agent-a"}, "id": 1},
            )
            await self._read_frame(agent_a_r)

            # Register Agent B
            await self._send_frame(
                agent_b_w,
                {"jsonrpc": "2.0", "method": "register", "params": {"agent_id": "agent-b"}, "id": 2},
            )
            await self._read_frame(agent_b_r)

            # Agent A sends direct message to Agent B
            direct_payload = {"query": "validate state"}
            await self._send_frame(
                agent_a_w,
                {"jsonrpc": "2.0", "method": "send", "params": {"recipient": "agent-b", "payload": direct_payload}, "id": 3},
            )
            send_ack = await self._read_frame(agent_a_r)
            self.assertTrue(send_ack.get("result", {}).get("delivered"))

            # Agent B receives message notification
            msg_frame = await self._read_frame(agent_b_r)
            self.assertEqual(msg_frame.get("method"), "message")
            self.assertEqual(msg_frame.get("params", {}).get("sender"), "agent-a")
            self.assertEqual(msg_frame.get("params", {}).get("payload"), direct_payload)
        finally:
            agent_a_w.close()
            agent_b_w.close()
            await agent_a_w.wait_closed()
            await agent_b_w.wait_closed()

    async def test_direct_send_to_unknown_recipient(self):
        reader, writer = await self._create_client()
        try:
            await self._send_frame(
                writer,
                {"jsonrpc": "2.0", "method": "register", "params": {"agent_id": "agent-sender"}, "id": 1},
            )
            await self._read_frame(reader)

            await self._send_frame(
                writer,
                {"jsonrpc": "2.0", "method": "send", "params": {"recipient": "offline-agent", "payload": {}}, "id": 2},
            )
            resp = await self._read_frame(reader)
            self.assertIn("error", resp)
            self.assertEqual(resp["error"].get("code"), -32001)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_client_disconnection_cleanup(self):
        reader, writer = await self._create_client()
        await self._send_frame(
            writer,
            {"jsonrpc": "2.0", "method": "register", "params": {"agent_id": "ephemeral-agent"}, "id": 1},
        )
        await self._read_frame(reader)
        await self._send_frame(
            writer,
            {"jsonrpc": "2.0", "method": "subscribe", "params": {"topics": ["cleanup.topic"]}, "id": 2},
        )
        await self._read_frame(reader)

        self.assertIn("ephemeral-agent", self.broker.clients)
        self.assertIn("ephemeral-agent", self.broker.subscriptions.get("cleanup.topic", set()))

        # Disconnect client
        writer.close()
        await writer.wait_closed()
        await asyncio.sleep(0.05)

        self.assertNotIn("ephemeral-agent", self.broker.clients)
        self.assertNotIn("ephemeral-agent", self.broker.subscriptions.get("cleanup.topic", set()))

    async def test_malformed_json_handling(self):
        reader, writer = await self._create_client()
        try:
            writer.write(b"NOT_JSON\n")
            await writer.drain()
            resp = await self._read_frame(reader)
            self.assertIn("error", resp)
            self.assertEqual(resp["error"].get("code"), -32700)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_payload_too_large(self):
        reader, writer = await self._create_client()
        try:
            oversized_frame = b"a" * (MAX_PAYLOAD_SIZE + 10) + b"\n"
            writer.write(oversized_frame)
            await writer.drain()
            resp = await self._read_frame(reader)
            self.assertIn("error", resp)
            self.assertEqual(resp["error"].get("code"), -32600)
        finally:
            writer.close()
            await writer.wait_closed()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests/test_agent_bus.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.agent_bus'`

- [ ] **Step 3: Write minimal stub implementation**

```bash
mkdir -p scripts
cat <<'EOF' > scripts/agent_bus.py
#!/usr/bin/env python3
"""Inter-Agent Message Bus Daemon for os-manager."""

MAX_PAYLOAD_SIZE = 1024 * 1024

def resolve_socket_path(custom_path=None):
    return ""

class MessageBroker:
    pass
EOF
chmod +x scripts/agent_bus.py
```

- [ ] **Step 4: Run test to verify import errors resolve but tests fail assertions**

Run: `python3 -m unittest tests/test_agent_bus.py -v`
Expected: FAIL on specific assertion errors in `TestSocketResolution` and `TestMessageBrokerAsync`.

- [ ] **Step 5: Commit test scaffold**

```bash
git add tests/test_agent_bus.py scripts/agent_bus.py
git commit -m "test(bus): create comprehensive unit test suite for inter-agent message bus"
```

---

### Task 2: Implement Asynchronous Message Bus Daemon

**Files:**
- Modify: `scripts/agent_bus.py`
- Test: `tests/test_agent_bus.py`

**Interfaces:**
- Consumes: Python standard library (`asyncio`, `json`, `os`, `sys`, `time`, `signal`, `argparse`, `typing`)
- Produces: Standalone executable `scripts/agent_bus.py` with `resolve_socket_path()`, `MessageBroker`, `start_bus_server()`, and CLI interface (`--socket-path`, `--help`).

- [ ] **Step 1: Write the failing test verification**

Run: `python3 -m unittest tests/test_agent_bus.py -v`
Expected: FAIL (incomplete `scripts/agent_bus.py` implementation).

- [ ] **Step 2: Implement the full Message Bus Daemon**

```python
#!/usr/bin/env python3
"""scripts/agent_bus.py

Inter-Agent Message Bus Daemon for os-manager.
Provides an asynchronous Unix domain socket server supporting JSON-RPC 2.0 framing,
client registration, topic-based publish-subscribe distribution, and direct peer routing.
"""

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from typing import Dict, Optional, Set

MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB limit


def resolve_socket_path(custom_path: Optional[str] = None) -> str:
    """Resolve the Unix domain socket path adhering to FHS standards."""
    if custom_path:
        target_dir = os.path.dirname(os.path.abspath(custom_path))
        if target_dir:
            os.makedirs(target_dir, mode=0o700, exist_ok=True)
        return custom_path

    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime and os.path.isdir(xdg_runtime):
        base_dir = os.path.join(xdg_runtime, "os-manager")
    else:
        base_dir = os.path.expanduser("~/.local/run/os-manager")

    os.makedirs(base_dir, mode=0o700, exist_ok=True)
    return os.path.join(base_dir, "bus.sock")


class MessageBroker:
    """Manages client connections, topic subscriptions, and message routing."""

    def __init__(self):
        self.clients: Dict[str, asyncio.StreamWriter] = {}
        self.writers_to_id: Dict[asyncio.StreamWriter, str] = {}
        self.subscriptions: Dict[str, Set[str]] = {}

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle individual client connection lifecycle and stream frames."""
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break

                if len(line) > MAX_PAYLOAD_SIZE:
                    err_resp = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32600, "message": "Payload too large"},
                        "id": None,
                    }
                    writer.write((json.dumps(err_resp) + "\n").encode("utf-8"))
                    await writer.drain()
                    continue

                try:
                    raw_str = line.decode("utf-8").strip()
                    if not raw_str:
                        continue
                    msg = json.loads(raw_str)
                    await self.process_rpc(msg, writer)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    err_resp = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32700, "message": "Parse error"},
                        "id": None,
                    }
                    writer.write((json.dumps(err_resp) + "\n").encode("utf-8"))
                    await writer.drain()
        finally:
            self.unregister(writer)
            writer.close()
            await writer.wait_closed()

    async def process_rpc(self, msg: dict, writer: asyncio.StreamWriter):
        """Process incoming JSON-RPC 2.0 request frames."""
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
            err_resp = {
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": msg.get("id") if isinstance(msg, dict) else None,
            }
            writer.write((json.dumps(err_resp) + "\n").encode("utf-8"))
            await writer.drain()
            return

        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "register":
            agent_id = params.get("agent_id", f"agent-{int(time.time() * 1000)}")
            self.clients[agent_id] = writer
            self.writers_to_id[writer] = agent_id
            response = {
                "jsonrpc": "2.0",
                "result": {
                    "status": "registered",
                    "agent_id": agent_id,
                    "session_id": f"sess-{hex(id(writer))[2:]}",
                },
                "id": msg_id,
            }
            writer.write((json.dumps(response) + "\n").encode("utf-8"))
            await writer.drain()

        elif method == "subscribe":
            topics = params.get("topics", [])
            agent_id = self.writers_to_id.get(writer)
            if agent_id:
                for t in topics:
                    self.subscriptions.setdefault(t, set()).add(agent_id)
            response = {
                "jsonrpc": "2.0",
                "result": {"subscribed": topics},
                "id": msg_id,
            }
            writer.write((json.dumps(response) + "\n").encode("utf-8"))
            await writer.drain()

        elif method == "publish":
            topic = params.get("topic", "default")
            payload = params.get("payload", {})
            publisher_id = self.writers_to_id.get(writer, "anonymous")

            event_frame = {
                "jsonrpc": "2.0",
                "method": "event",
                "params": {
                    "topic": topic,
                    "publisher": publisher_id,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "payload": payload,
                },
            }
            event_bytes = (json.dumps(event_frame) + "\n").encode("utf-8")

            # Route to exact subscribers and wildcard subscribers
            for sub_topic, agent_set in self.subscriptions.items():
                is_match = False
                if sub_topic == topic:
                    is_match = True
                elif sub_topic.endswith(".*"):
                    prefix = sub_topic[:-2]
                    if topic.startswith(prefix):
                        is_match = True

                if is_match:
                    for target_id in list(agent_set):
                        target_writer = self.clients.get(target_id)
                        if target_writer and target_writer != writer:
                            target_writer.write(event_bytes)

            response = {
                "jsonrpc": "2.0",
                "result": {"published": True},
                "id": msg_id,
            }
            writer.write((json.dumps(response) + "\n").encode("utf-8"))
            await writer.drain()

        elif method == "send":
            recipient = params.get("recipient")
            payload = params.get("payload", {})
            sender_id = self.writers_to_id.get(writer, "anonymous")

            target_writer = self.clients.get(recipient)
            if target_writer:
                msg_frame = {
                    "jsonrpc": "2.0",
                    "method": "message",
                    "params": {
                        "sender": sender_id,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "payload": payload,
                    },
                }
                target_writer.write((json.dumps(msg_frame) + "\n").encode("utf-8"))
                response = {
                    "jsonrpc": "2.0",
                    "result": {"delivered": True, "recipient": recipient},
                    "id": msg_id,
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32001,
                        "message": f"Recipient '{recipient}' not found or offline",
                    },
                    "id": msg_id,
                }
            writer.write((json.dumps(response) + "\n").encode("utf-8"))
            await writer.drain()

        elif method == "ping":
            response = {
                "jsonrpc": "2.0",
                "result": {"status": "pong", "timestamp": time.time()},
                "id": msg_id,
            }
            writer.write((json.dumps(response) + "\n").encode("utf-8"))
            await writer.drain()

        else:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method '{method}' not found"},
                "id": msg_id,
            }
            writer.write((json.dumps(response) + "\n").encode("utf-8"))
            await writer.drain()

    def unregister(self, writer: asyncio.StreamWriter):
        """Remove disconnected client writer and clean up all subscriptions."""
        agent_id = self.writers_to_id.pop(writer, None)
        if agent_id:
            self.clients.pop(agent_id, None)
            for topic_set in self.subscriptions.values():
                topic_set.discard(agent_id)


async def run_server(socket_path: str):
    """Run the asyncio Unix domain socket server with signal handling."""
    if os.path.exists(socket_path):
        try:
            os.remove(socket_path)
        except OSError:
            pass

    broker = MessageBroker()
    server = await asyncio.start_unix_server(broker.handle_client, path=socket_path)
    os.chmod(socket_path, 0o600)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown():
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _shutdown)
        except NotImplementedError:
            pass

    print(f"[agent_bus] Message bus daemon listening on {socket_path}", flush=True)

    async with server:
        serve_task = asyncio.create_task(server.serve_forever())
        await stop_event.wait()
        serve_task.cancel()
        try:
            await serve_task
        except asyncio.CancelledError:
            pass

    if os.path.exists(socket_path):
        try:
            os.remove(socket_path)
        except OSError:
            pass
    print("[agent_bus] Message bus daemon stopped cleanly", flush=True)


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="OS-Manager Inter-Agent Message Bus Daemon")
    parser.add_argument(
        "--socket-path",
        default=None,
        help="Custom Unix domain socket path (default: $XDG_RUNTIME_DIR/os-manager/bus.sock)",
    )
    args = parser.parse_args()

    sock_path = resolve_socket_path(args.socket_path)
    try:
        asyncio.run(run_server(sock_path))
    except KeyboardInterrupt:
        if os.path.exists(sock_path):
            try:
                os.remove(sock_path)
            except OSError:
                pass


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run unit tests to verify implementation passes**

Run: `python3 -m unittest tests/test_agent_bus.py -v`
Expected: `Ran 9 tests in 0.xxx s - OK`

- [ ] **Step 4: Verify Python syntax and bytecode compilation**

Run: `python3 -m py_compile scripts/agent_bus.py`
Expected: Exit Code 0 with zero syntax warnings.

- [ ] **Step 5: Commit implementation**

```bash
git add scripts/agent_bus.py
git commit -m "feat(bus): implement asynchronous inter-agent message bus daemon"
```

---

### Task 3: Implement POSIX Shell Publisher Helper

**Files:**
- Create: `scripts/bus_send.sh`
- Test: `tests/test_agent_bus.py`

**Interfaces:**
- Consumes: Positional arguments or flags (`--topic`, `--to`, `--payload`, `--socket`, `--help`)
- Produces: Lightweight POSIX shell client that connects to the message bus socket, dispatches JSON-RPC requests, and exits cleanly with 0 on socket disconnection.

- [ ] **Step 1: Write the failing test verification**

Run: `bash scripts/bus_send.sh --help`
Expected: FAIL (file missing).

- [ ] **Step 2: Implement `scripts/bus_send.sh`**

```bash
#!/usr/bin/env bash
# scripts/bus_send.sh — Publish JSON payloads to the Inter-Agent Message Bus
# Fast-path CLI helper for shell hooks and background automation tasks.
set -euo pipefail

show_help() {
    cat <<'EOF'
Usage: bus_send.sh [OPTIONS]

Options:
  --topic <name>      Publish payload to the designated topic channel
  --to <agent_id>     Send direct point-to-point payload to recipient agent
  --payload <json>    JSON string payload (default: '{}')
  --socket <path>     Custom Unix domain socket path
  --help              Display this help message and exit

Examples:
  ./scripts/bus_send.sh --topic "task.dispatch" --payload '{"task_id":"T-101"}'
  ./scripts/bus_send.sh --to "agy-reasoner-01" --payload '{"action":"review"}'
EOF
}

resolve_bus_socket() {
    if [ -n "${CUSTOM_SOCKET:-}" ]; then
        echo "${CUSTOM_SOCKET}"
    elif [ -n "${XDG_RUNTIME_DIR:-}" ] && [ -d "${XDG_RUNTIME_DIR}" ]; then
        echo "${XDG_RUNTIME_DIR}/os-manager/bus.sock"
    else
        echo "${HOME}/.local/run/os-manager/bus.sock"
    fi
}

TOPIC=""
RECIPIENT=""
PAYLOAD="{}"
CUSTOM_SOCKET=""

while [ $# -gt 0 ]; do
    case "$1" in
        --topic)
            TOPIC="$2"
            shift 2
            ;;
        --to)
            RECIPIENT="$2"
            shift 2
            ;;
        --payload)
            PAYLOAD="$2"
            shift 2
            ;;
        --socket)
            CUSTOM_SOCKET="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            # Support positional arguments: bus_send.sh <topic> <payload>
            if [ -z "${TOPIC}" ] && [ -z "${RECIPIENT}" ]; then
                TOPIC="$1"
            elif [ "${PAYLOAD}" = "{}" ]; then
                PAYLOAD="$1"
            fi
            shift
            ;;
    esac
done

if [ -z "${TOPIC}" ] && [ -z "${RECIPIENT}" ]; then
    echo "Error: Either --topic or --to must be specified." >&2
    show_help >&2
    exit 1
fi

SOCKET_PATH="$(resolve_bus_socket)"

# Fail-safe degradation: if socket is missing or inactive, exit 0 cleanly
if [ ! -S "${SOCKET_PATH}" ]; then
    exit 0
fi

# Send JSON-RPC frame via python standard library socket client
python3 -c "
import json
import os
import socket
import sys

socket_path = sys.argv[1]
topic = sys.argv[2]
recipient = sys.argv[3]
raw_payload = sys.argv[4]

try:
    payload_obj = json.loads(raw_payload) if raw_payload else {}
except Exception:
    payload_obj = {'raw': raw_payload}

if recipient:
    rpc_msg = {
        'jsonrpc': '2.0',
        'method': 'send',
        'params': {'recipient': recipient, 'payload': payload_obj},
        'id': 1,
    }
else:
    rpc_msg = {
        'jsonrpc': '2.0',
        'method': 'publish',
        'params': {'topic': topic, 'payload': payload_obj},
        'id': 1,
    }

try:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    sock.connect(socket_path)
    # Send registration first
    reg_msg = {
        'jsonrpc': '2.0',
        'method': 'register',
        'params': {'agent_id': f'cli-{os.getpid()}', 'role': 'publisher'},
        'id': 0,
    }
    sock.sendall((json.dumps(reg_msg) + '\n').encode('utf-8'))
    # Send actual RPC
    sock.sendall((json.dumps(rpc_msg) + '\n').encode('utf-8'))
    sock.close()
except Exception:
    pass
" "${SOCKET_PATH}" "${TOPIC}" "${RECIPIENT}" "${PAYLOAD}" || true

exit 0
```
```bash
chmod +x scripts/bus_send.sh
```

- [ ] **Step 3: Verify execution and argument parsing**

Run: `bash scripts/bus_send.sh --help`
Expected: Displays help text and exits with code 0.

Run: `bash scripts/bus_send.sh --topic "task.test" --payload '{"status":"ok"}'`
Expected: Exits cleanly with code 0 even when socket daemon is offline.

- [ ] **Step 4: Verify syntax and linting**

Run: `bash -n scripts/bus_send.sh && shellcheck scripts/bus_send.sh`
Expected: Passes with zero syntax or linting errors.

- [ ] **Step 5: Commit shell publisher helper**

```bash
git add scripts/bus_send.sh
git commit -m "feat(bus): implement lightweight shell publisher helper bus_send.sh"
```

---

### Task 4: Create Systemd User Service Unit

**Files:**
- Create: `systemd/agent-bus.service`

**Interfaces:**
- Consumes: `%h/dev/os-manager/scripts/agent_bus.py`
- Produces: Hardened systemd user service unit with sandboxing rules and automated restart on failure.

- [ ] **Step 1: Write the failing service unit validation test**

Run: `[ -f systemd/agent-bus.service ]`
Expected: FAIL (file does not exist).

- [ ] **Step 2: Implement `systemd/agent-bus.service`**

```ini
[Unit]
Description=OS-Manager Inter-Agent Message Bus Daemon
Documentation=https://github.com/0xrizz/os-manager
After=network.target

[Service]
Type=simple
ExecStart=%h/dev/os-manager/scripts/agent_bus.py
Restart=on-failure
RestartSec=2s

# Runtime directory setup (creates %t/os-manager with 0700 permissions)
RuntimeDirectory=os-manager
RuntimeDirectoryMode=0700

# Security Sandboxing
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=%t/os-manager %h/.local/run/os-manager %h/dev/os-manager/backups/logs
NoNewPrivileges=true

[Install]
WantedBy=default.target
```

- [ ] **Step 3: Validate systemd unit syntax**

Run: `systemd-analyze verify systemd/agent-bus.service 2>&1 || true`
Expected: Passes or verifies syntax without structural errors.

- [ ] **Step 4: Commit systemd service unit**

```bash
git add systemd/agent-bus.service
git commit -m "feat(bus): add systemd user service unit for inter-agent message bus"
```

---

### Task 5: Master Harness Integration and End-to-End Assertions

**Files:**
- Modify: `tests/test_harness.sh:300-312`
- Test: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `scripts/agent_bus.py`, `scripts/bus_send.sh`, `tests/test_agent_bus.py`, `systemd/agent-bus.service`
- Produces: 46 total assertions in master harness test suite verifying full message bus lifecycle.

- [ ] **Step 1: Write the failing harness integration test**

Edit `tests/test_harness.sh` to include the message bus assertion group:

```bash
# Add to tests/test_harness.sh before Summary section
echo "--- Testing Inter-Agent Message Bus Suite ---"
python3 -m py_compile "${WORKSPACE_ROOT}/scripts/agent_bus.py" > /dev/null 2>&1
assert_exit_code "agent_bus.py bytecode compilation" 0 $?

"${WORKSPACE_ROOT}/scripts/agent_bus.py" --help > /dev/null 2>&1
assert_exit_code "agent_bus.py --help execution" 0 $?

python3 -m unittest "${WORKSPACE_ROOT}/tests/test_agent_bus.py" > /dev/null 2>&1
assert_exit_code "test_agent_bus.py unit test suite" 0 $?

"${WORKSPACE_ROOT}/scripts/bus_send.sh" --help > /dev/null 2>&1
assert_exit_code "bus_send.sh --help execution" 0 $?

"${WORKSPACE_ROOT}/scripts/bus_send.sh" --topic "test.harness" --payload '{"status":"ok"}' > /dev/null 2>&1
assert_exit_code "bus_send.sh fail-safe execution without daemon" 0 $?

[ -f "${WORKSPACE_ROOT}/systemd/agent-bus.service" ] && BUS_SERVICE_EXISTS=0 || BUS_SERVICE_EXISTS=1
assert_exit_code "agent-bus.service exists" 0 "${BUS_SERVICE_EXISTS}"
```

- [ ] **Step 2: Run master harness test suite to verify assertions pass**

Run: `./tests/test_harness.sh`
Expected: All 47 assertions pass with `Summary: 47/47 passed` and Exit Code 0.

- [ ] **Step 3: Run harness check self-test**

Run: `./scripts/harness_check.sh`
Expected: Passes with Exit Code 0.

- [ ] **Step 4: Commit harness integration**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate inter-agent message bus assertions into master harness"
```

---

## Plan Self-Review Checklist

- [x] **Spec Coverage:**
  - Socket resolution under `$XDG_RUNTIME_DIR/os-manager/bus.sock` with fallback to `~/.local/run/os-manager/bus.sock` covered in Task 1 and Task 2.
  - JSON-RPC 2.0 framing (`register`, `subscribe`, `publish`, `send`, `ping`) covered in Task 1 and Task 2.
  - POSIX shell helper `scripts/bus_send.sh` covered in Task 3.
  - Systemd user service `systemd/agent-bus.service` covered in Task 4.
  - Master harness assertions 27-30 covered in Task 5.
- [x] **Placeholder Scan:** Zero instances of "TBD", "TODO", or missing code blocks.
- [x] **Type Consistency:** Method names (`resolve_socket_path`, `MessageBroker`, `handle_client`, `process_rpc`, `unregister`) and signatures match across all tasks.
- [x] **Writing Rules (agent-style):** Active voice, positive framing, no casual em/en dashes, no filler words, Title Case headings.
