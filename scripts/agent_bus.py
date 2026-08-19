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
import time

MAX_PAYLOAD_SIZE = 1024 * 1024  # 1MB limit


def resolve_socket_path(custom_path: str | None = None) -> str:
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
        self.clients: dict[str, asyncio.StreamWriter] = {}
        self.writers_to_id: dict[asyncio.StreamWriter, str] = {}
        self.subscriptions: dict[str, set[str]] = {}

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle individual client connection lifecycle and stream frames."""
        try:
            while True:
                try:
                    line = await reader.readline()
                except (ValueError, asyncio.LimitOverrunError):
                    err_resp = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32600, "message": "Payload too large"},
                        "id": None,
                    }
                    try:
                        writer.write((json.dumps(err_resp) + "\n").encode("utf-8"))
                        await writer.drain()
                    except Exception:
                        pass
                    break

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
            try:
                await writer.wait_closed()
            except Exception:
                pass

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
                    namespace = sub_topic[:-1]  # e.g. "task."
                    if topic.startswith(namespace) or topic == sub_topic[:-2]:
                        is_match = True

                if is_match:
                    for target_id in list(agent_set):
                        target_writer = self.clients.get(target_id)
                        if target_writer and target_writer != writer:
                            try:
                                target_writer.write(event_bytes)
                            except Exception:
                                pass

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
                try:
                    target_writer.write((json.dumps(msg_frame) + "\n").encode("utf-8"))
                except Exception:
                    pass
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
            if self.clients.get(agent_id) is writer:
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
    server = await asyncio.start_unix_server(broker.handle_client, path=socket_path, limit=MAX_PAYLOAD_SIZE * 2)
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
