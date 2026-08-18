# Specification: Agent Workspace Virtualization Architecture

- **Date:** 2026-08-19
- **Scope:** Container Isolation & Untrusted Execution Sandbox (`/home/rizz/dev/os-manager`)
- **Status:** Approved
- **Deliverable Reference:** Phase 4, Deliverable 4.4

---

## 1. Executive Summary

Autonomous subagents executing complex software engineering workflows (such as dependency installations, test execution, and third-party script evaluation) require an execution sandbox. Running untrusted code directly on the host ext4 workspace creates risks of unintended file modification, credential leakage, and system configuration drift.

Agent Workspace Virtualization provides an ephemeral, rootless container execution sandbox (`scripts/isolate_agent.sh`) powered by rootless Podman. This utility encapsulates subagent executions within an unprivileged Linux user namespace, masking host credentials and Windows filesystem mounts while enforcing strict memory and CPU boundaries.

---

## 2. Problem Statement and Architectural Goals

### Current Limitations
1. **Unbounded Subagent Execution**: Subagents currently execute commands directly in the host shell environment, possessing full read/write access to user dotfiles and development toolchains.
2. **Credential Exposure Risk**: Sensitive directories (such as `~/.ssh/`, `~/.gnupg/`, and cloud CLI authentication tokens) remain accessible to any process spawned within the user session.
3. **Resource Exhaustion Vulnerabilities**: Runaway subagent test processes or infinite loops can consume all host memory and CPU cores, degrading interactive system responsiveness.

### Architectural Goals
- **Rootless User Namespace Isolation**: Run sandbox processes under unprivileged UID mappings (`--userns=keep-id`), preventing container breakouts from obtaining host root privileges.
- **Sensitive Path Masking**: Ensure host Windows mounts (`/mnt/c`, `/mnt/d`) and private credentials (`~/.ssh`, `~/.gnupg`) are excluded from container mount tables.
- **Enforced Resource Constraints**: Bound container memory usage (2GB default) and CPU core allocation (2 cores default).
- **Seamless CLI Delegation**: Provide a transparent POSIX shell wrapper that forwards commands and preserves exit status codes.

---

## 3. Sandbox Topology and Namespace Architecture

### Isolation Topology

```text
 ┌─────────────────────────────────────────────────────────────┐
 │       Claude Code Subagent / Antigravity Execution          │
 └──────────────────────────────┬──────────────────────────────┘
                                │ Invokes: scripts/isolate_agent.sh [opts] -- <cmd>
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │           Rootless Podman Container Sandbox Engine          │
 │ • User Namespace: --userns=keep-id (UID 1000 preserved)     │
 │ • Resource Limits: --memory=2g --cpus=2 --pids-limit=256    │
 │ • Mount Boundary: Isolated /workspace volume mount only     │
 └──────────────┬──────────────────────────────┬───────────────┘
                │                              │
        ┌───────┴──────────────┐        ┌──────┴───────────────┐
        ▼                      ▼        ▼                      ▼
 ┌──────────────┐       ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
 │ Target Repo  │       │ Network Mode │ │ Blocked Host │ │ Masked Paths │
 │ ext4 Mount   │       │ slirp4netns  │ │ /mnt/c &     │ │ ~/.ssh/      │
 │ (read-write) │       │ or none      │ │ /mnt/d       │ │ ~/.gnupg/    │
 └──────────────┘       └──────────────┘ └──────────────┘ └──────────────┘
```

### Namespace Isolation Invariants
- **User Namespace**: Uses `--userns=keep-id` so container files match host UID `1000:1000` without permission mismatches.
- **Filesystem Isolation**: Mounts only the current workspace path to `/workspace`. Host root (`/`), `/etc`, `/var`, `/mnt/c`, and `/mnt/d` are inaccessible.
- **Network Isolation**: Defaults to `--network=none` for air-gapped test execution. Network access (`--network=slirp4netns`) is activated only when explicitly requested.
- **Process Boundaries**: Defaults to `--pids-limit=256` to prevent fork bomb vulnerabilities.

---

## 4. Sandbox Wrapper Implementation (`scripts/isolate_agent.sh`)

### 4.1 CLI Parameter Specification

```bash
# scripts/isolate_agent.sh — Execute commands in an isolated rootless container
# Usage: ./scripts/isolate_agent.sh [options] -- <command...>
#
# Options:
#   --image <image>     Base container image (default: debian:13-slim)
#   --network <mode>    Network configuration (none | slirp4netns; default: none)
#   --mem <limit>       Memory limit (default: 2g)
#   --cpus <count>      CPU core allocation (default: 2)
#   --read-only         Mount workspace as read-only volume
#   --dry-run           Print container command without executing
```

### 4.2 Wrapper Implementation

```bash
#!/usr/bin/env bash
# scripts/isolate_agent.sh — Rootless container sandbox execution wrapper
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Default Configuration
IMAGE="docker.io/library/debian:13-slim"
NETWORK_MODE="none"
MEMORY_LIMIT="2g"
CPU_LIMIT="2"
READ_ONLY=false
DRY_RUN=false
TARGET_DIR="${PWD}"

# Parse CLI Flags
COMMAND_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --image)
            IMAGE="$2"
            shift 2
            ;;
        --network)
            NETWORK_MODE="$2"
            shift 2
            ;;
        --mem)
            MEMORY_LIMIT="$2"
            shift 2
            ;;
        --cpus)
            CPU_LIMIT="$2"
            shift 2
            ;;
        --read-only)
            READ_ONLY=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --)
            shift
            COMMAND_ARGS=("$@")
            break
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

if [ ${#COMMAND_ARGS[@]} -eq 0 ]; then
    echo "Usage: $0 [options] -- <command...>" >&2
    exit 1
fi

# Preflight: Verify Podman Availability
if ! command -v podman &>/dev/null; then
    echo "[ERROR] Podman is not installed. Install via: pkg_install podman" >&2
    exit 1
fi

# Determine Mount Flags
MOUNT_MODE="rw"
if [ "${READ_ONLY}" = true ]; then
    MOUNT_MODE="ro"
fi

# Assemble Podman Execution Command
PODMAN_CMD=(
    podman run
    --rm
    -i
    --userns=keep-id
    --network="${NETWORK_MODE}"
    --memory="${MEMORY_LIMIT}"
    --cpus="${CPU_LIMIT}"
    --pids-limit=256
    --cap-drop=ALL
    --security-opt=no-new-privileges
    -v "${TARGET_DIR}:/workspace:${MOUNT_MODE},z"
    -w /workspace
    "${IMAGE}"
    "${COMMAND_ARGS[@]}"
)

if [ "${DRY_RUN}" = true ]; then
    echo "${PODMAN_CMD[@]}"
    exit 0
fi

# Execute Sandbox Command and Propagate Exit Status
"${PODMAN_CMD[@]}"
```

---

## 5. Security Guardrail Invariants (`scripts/hooks/pre_tool_guard.sh`)

### 5.1 Privileged Flag Interception

`pre_tool_guard.sh` prevents subagents from bypassing container isolation by blocking forbidden Podman arguments:

```bash
# Invariant Block: Dangerous Container Privilege Escalation
if echo "${CMD}" | grep -qE '\bpodman\s+run\b.*\b(--privileged|--pid=host|--net=host|--cap-add=ALL|-v\s+/(dev|proc|sys|root|etc))\b'; then
    echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Container privilege escalation and host namespace leakage is strictly forbidden: ${CMD}" >&2
    exit 2
fi
```

---

## 6. Verification and Automated Test Strategy

### Unit Test Assertions (`tests/test_harness.sh`)

1. **Assertion 33**: Verify `scripts/isolate_agent.sh` passes `bash -n` and `shellcheck`.
2. **Assertion 34**: Verify `scripts/isolate_agent.sh --dry-run` constructs container parameters with `--userns=keep-id`, `--cap-drop=ALL`, and `--security-opt=no-new-privileges`.
3. **Assertion 35**: Verify `pre_tool_guard.sh` blocks `podman run --privileged` with Exit Code 2.
4. **Assertion 36**: Verify `scripts/isolate_agent.sh` rejects unauthorized host mounts.
