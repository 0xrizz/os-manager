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
            self.broker.handle_client, path=self.socket_path, limit=MAX_PAYLOAD_SIZE * 2
        )

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        self.tmp_dir.cleanup()

    async def _create_client(self):
        return await asyncio.open_unix_connection(
            self.socket_path, limit=MAX_PAYLOAD_SIZE * 2
        )

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
