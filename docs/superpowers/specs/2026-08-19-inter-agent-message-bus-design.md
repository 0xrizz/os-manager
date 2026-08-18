# Specification: Inter-Agent Message Bus Architecture

- **Date:** 2026-08-19
- **Scope:** Multi-Agent Communication and Event Routing (`/home/rizz/dev/os-manager`)
- **Status:** Approved
- **Deliverable Reference:** Phase 4, Deliverable 4.2

---

## 1. Executive Summary

As development workflows scale across multiple autonomous agents (Claude Code subagents, Google Antigravity `agy`, and background task runners), agents require a structured, low-latency communication layer.

The Inter-Agent Message Bus introduces an asynchronous message broker (`scripts/agent_bus.py`) bound to a local Unix domain socket at `$XDG_RUNTIME_DIR/os-manager/bus.sock` (with fallback to `~/.local/run/os-manager/bus.sock`). This broker enables publish-subscribe event distribution, direct peer routing, and structured JSON-RPC 2.0 message framing across independent terminal processes without symlink hijacking risks.

---

## 2. Problem Statement and Architectural Goals

### Current Limitations
1. **Isolated Agent Execution**: Subagents operating in separate tmux panes or background processes lack a direct mechanism to exchange intermediate task states.
2. **File-Polling Bottlenecks**: State synchronization currently relies on disk files, introducing filesystem latency and file locking contention.
3. **Unstructured Telemetry**: Multi-agent events are captured across disparate log files without unified event correlation.
4. **Temporary Directory Insecurity**: Placing shared domain sockets in global `/tmp` exposes services to symlink collision and auto-cleanup purging during periodic maintenance.

### Architectural Goals
- **Sub-Millisecond Message Delivery**: Deliver structured messages between agents with minimal latency over a secure Unix domain socket.
- **FHS-Compliant Socket Paths**: Bind sockets strictly under `$XDG_RUNTIME_DIR/os-manager/` (fallback `~/.local/run/os-manager/`) with `0700` directory and `0600` socket permissions.
- **Standards-Compliant RPC Framing**: Use newline-delimited JSON-RPC 2.0 envelopes for all socket interactions.
- **Decoupled Event Distribution**: Support both topic-based publish-subscribe patterns and direct point-to-point agent messaging.
- **Fail-Safe Non-Blocking Design**: Ensure calling scripts and lifecycle hooks degrade gracefully when the message daemon is offline.

---

## 3. Message Bus Architecture and Socket Topology

### System Topology

```text
 ┌─────────────────────────────────────────────────────────────┐
 │               Claude Code Subagents & Harness               │
 └──────────────────────────────┬──────────────────────────────┘
                                │ JSON-RPC 2.0 (Unix Socket)
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │       Inter-Agent Message Bus (scripts/agent_bus.py)        │
 │ • asyncio stream server on $XDG_RUNTIME_DIR/os-manager/bus.sock │
 │ • Topic Pub/Sub engine & Point-to-Point routing             │
 │ • In-memory ring buffer (1000 items) & Dead-Letter queue    │
 └──────────────┬──────────────────────────────┬───────────────┘
                │                              │
                ▼                              ▼
 ┌──────────────────────────────┐ ┌────────────────────────────┐
 │  Google Antigravity Worker   │ │  System Telemetry Logger   │
 │  (agy background adapter)    │ │  (backups/logs/agent_bus)  │
 └──────────────────────────────┘ └────────────────────────────┘
```

### Transport and Socket Invariants
- **Primary Socket Path**: `$XDG_RUNTIME_DIR/os-manager/bus.sock` (typically `/run/user/1000/os-manager/bus.sock`)
- **Fallback Socket Path**: `~/.local/run/os-manager/bus.sock`
- **Directory Permissions**: `0700` (restricted exclusively to the owning user)
- **Socket Permissions**: `0600`
- **Protocol Framing**: Newline-delimited JSON (`\n`) UTF-8 text streams
- **Maximum Frame Size**: 1 megabyte per message frame

---

## 4. Protocol Specification (JSON-RPC 2.0)

All message frames follow the JSON-RPC 2.0 specification.

### 4.1 Client Registration (`register`)

Clients register their unique identifier and operational role upon connection:

```json
{
  "jsonrpc": "2.0",
  "method": "register",
  "params": {
    "agent_id": "claude-worker-01",
    "role": "implementer",
    "pid": 48210
  },
  "id": 1
}
```

Response:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "registered",
    "agent_id": "claude-worker-01",
    "session_id": "sess-9a4f2"
  },
  "id": 1
}
```

### 4.2 Topic Subscription (`subscribe`)

Clients subscribe to exact topics or wildcard patterns (for example, `task.*`):

```json
{
  "jsonrpc": "2.0",
  "method": "subscribe",
  "params": {
    "topics": ["task.dispatch", "telemetry.*"]
  },
  "id": 2
}
```

Response:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "subscribed": ["task.dispatch", "telemetry.*"]
  },
  "id": 2
}
```

### 4.3 Topic Event Publication (`publish`)

Clients publish broadcast events to specific topic channels:

```json
{
  "jsonrpc": "2.0",
  "method": "publish",
  "params": {
    "topic": "task.dispatch",
    "payload": {
      "task_id": "T-104",
      "target_file": "scripts/lib/distro.sh",
      "action": "validate"
    }
  },
  "id": 3
}
```

Broadcast Notification to Subscribers:
```json
{
  "jsonrpc": "2.0",
  "method": "event",
  "params": {
    "topic": "task.dispatch",
    "publisher": "claude-worker-01",
    "timestamp": "2026-08-19T04:12:00.124850Z",
    "payload": {
      "task_id": "T-104",
      "target_file": "scripts/lib/distro.sh",
      "action": "validate"
    }
  }
}
```

### 4.4 Direct Peer Messaging (`send`)

Clients send point-to-point requests directly to a designated `agent_id`:

```json
{
  "jsonrpc": "2.0",
  "method": "send",
  "params": {
    "recipient": "agy-reasoner-01",
    "payload": {
      "query": "verify architectural boundary for distro.sh"
    }
  },
  "id": 4
}
```

---

## 5. Daemon and Client Helper Implementation

### 5.1 Python Async Daemon (`scripts/agent_bus.py`)

The daemon implementation uses Python's standard library `asyncio` and resolves paths dynamically:

```python
#!/usr/bin/env python3
"""Inter-Agent Message Bus Daemon for os-manager."""

import asyncio
import json
import os
import sys
import time
from typing import Dict, Set

def resolve_socket_path() -> str:
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime and os.path.isdir(xdg_runtime):
        base = os.path.join(xdg_runtime, "os-manager")
    else:
        base = os.path.expanduser("~/.local/run/os-manager")
    os.makedirs(base, mode=0o700, exist_ok=True)
    return os.path.join(base, "bus.sock")

SOCKET_PATH = resolve_socket_path()
LOG_FILE = "backups/logs/agent_bus.jsonl"
MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB


class MessageBroker:
    def __init__(self):
        self.clients: Dict[str, asyncio.StreamWriter] = {}
        self.subscriptions: Dict[str, Set[str]] = {}
        self.writers_to_id: Dict[asyncio.StreamWriter, str] = {}

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break

                if len(line) > MAX_PAYLOAD_SIZE:
                    writer.write(b'{"jsonrpc":"2.0","error":{"code":-32600,"message":"Payload too large"}}\n')
                    await writer.drain()
                    continue

                try:
                    msg = json.loads(line.decode("utf-8"))
                    await self.process_rpc(msg, writer)
                except json.JSONDecodeError:
                    writer.write(b'{"jsonrpc":"2.0","error":{"code":-32700,"message":"Parse error"}}\n')
                    await writer.drain()

        finally:
            self.unregister(writer)
            writer.close()
            await writer.wait_closed()

    async def process_rpc(self, msg: dict, writer: asyncio.StreamWriter):
        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "register":
            agent_id = params.get("agent_id", f"agent-{int(time.time())}")
            self.clients[agent_id] = writer
            self.writers_to_id[writer] = agent_id
            response = {
                "jsonrpc": "2.0",
                "result": {"status": "registered", "agent_id": agent_id},
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
            for sub_topic, agent_set in self.subscriptions.items():
                if sub_topic == topic or (sub_topic.endswith(".*") and topic.startswith(sub_topic[:-2])):
                    for target_id in agent_set:
                        if target_id in self.clients:
                            self.clients[target_id].write(event_bytes)

            writer.write((json.dumps({"jsonrpc": "2.0", "result": {"published": True}, "id": msg_id}) + "\n").encode("utf-8"))
            await writer.drain()

        elif method == "subscribe":
            topics = params.get("topics", [])
            agent_id = self.writers_to_id.get(writer)
            if agent_id:
                for t in topics:
                    self.subscriptions.setdefault(t, set()).add(agent_id)
            writer.write((json.dumps({"jsonrpc": "2.0", "result": {"subscribed": topics}, "id": msg_id}) + "\n").encode("utf-8"))
            await writer.drain()

    def unregister(self, writer: asyncio.StreamWriter):
        agent_id = self.writers_to_id.pop(writer, None)
        if agent_id:
            self.clients.pop(agent_id, None)
            for topic_set in self.subscriptions.values():
                topic_set.discard(agent_id)


async def main():
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)

    broker = MessageBroker()
    server = await asyncio.start_unix_server(broker.handle_client, path=SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o600)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
```

### 5.2 POSIX Shell Helper (`scripts/bus_send.sh`)

A lightweight POSIX shell helper for publishing events from hooks and automation scripts:

```bash
#!/usr/bin/env bash
# scripts/bus_send.sh — Publish JSON payloads to the Inter-Agent Message Bus
set -euo pipefail

resolve_bus_socket() {
    if [ -n "${XDG_RUNTIME_DIR:-}" ] && [ -d "${XDG_RUNTIME_DIR}" ]; then
        echo "${XDG_RUNTIME_DIR}/os-manager/bus.sock"
    else
        echo "${HOME}/.local/run/os-manager/bus.sock"
    fi
}

SOCKET_PATH="$(resolve_bus_socket)"

if [ $# -lt 2 ]; then
    echo "Usage: $0 <topic> <json_payload>" >&2
    exit 1
fi

TOPIC="$1"
PAYLOAD="$2"

if [ ! -S "${SOCKET_PATH}" ]; then
    # Degrade gracefully without failing caller
    exit 0
fi

python3 -c "
import socket, json, sys

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
try:
    sock.connect('${SOCKET_PATH}')
    msg = {
        'jsonrpc': '2.0',
        'method': 'publish',
        'params': {
            'topic': sys.argv[1],
            'payload': json.loads(sys.argv[2])
        },
        'id': 1
    }
    sock.sendall((json.dumps(msg) + '\n').encode('utf-8'))
finally:
    sock.close()
" "${TOPIC}" "${PAYLOAD}" || true
```

---

## 6. Systemd Integration and Service Unit

### Unit Definition (`systemd/agent-bus.service`)

```ini
[Unit]
Description=OS-Manager Inter-Agent Message Bus Daemon
After=network.target

[Service]
Type=simple
ExecStart=%h/dev/os-manager/scripts/agent_bus.py
Restart=on-failure
RestartSec=2s

# Security Sandboxing
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=%t/os-manager %h/.local/run/os-manager %h/dev/os-manager/backups/logs
NoNewPrivileges=true

[Install]
WantedBy=default.target
```

---

## 7. Verification and Automated Test Strategy

### Unit Test Assertions (`tests/test_harness.sh`)

1. **Assertion 27**: Verify daemon initialization creates `bus.sock` under `$XDG_RUNTIME_DIR/os-manager/` (or `~/.local/run/os-manager/`) with `0600` permissions.
2. **Assertion 28**: Verify client registration handshake over the secure Unix socket.
3. **Assertion 29**: Verify pub/sub broadcast delivery to subscribed topic listeners.
4. **Assertion 30**: Verify `scripts/bus_send.sh` executes cleanly and degrades gracefully when the socket is unavailable.

---

## 8. Rollout Sequence and Implementation DAG

The Inter-Agent Message Bus belongs to Stage 3 of the implementation plan:

1. **Stage 1 (Foundation Libraries and Tracing)**:
   - Deliverable 3.4: Hook Performance Tracing (`scripts/hooks/lib/trace_helper.sh`, `scripts/hook_benchmark.sh`).
   - Deliverable 4.1: Cross-Distribution Engine (`scripts/lib/distro.sh`, generalized package guardrails).
2. **Stage 2 (Base System Services, Notifications, and Sandbox)**:
   - Deliverable 3.1: Prometheus Metrics Exporter (`scripts/metrics_exporter.py`).
   - Deliverable 3.3: Desktop Notification Bridge (`scripts/notify_host.sh`).
   - Deliverable 3.2: Automated Host Disk Compaction (`scripts/compact_host_disk.sh`).
   - Deliverable 4.4: Agent Workspace Virtualization (`scripts/sandbox_exec.sh`).
3. **Stage 3 (Multi-Agent Mesh and Disaster Recovery)**:
   - Deliverable 4.2: Inter-Agent Message Bus (`scripts/agent_bus.py`, `scripts/bus_send.sh`).
   - Deliverable 4.3: Automated Disaster Recovery Provisioning (`scripts/bootstrap_wsl.ps1`, `scripts/post_bootstrap.sh`).
