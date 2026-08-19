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
