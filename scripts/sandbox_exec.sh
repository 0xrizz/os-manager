#!/usr/bin/env bash
# scripts/sandbox_exec.sh - Rootless container sandbox execution wrapper
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC2034
_WORKSPACE="${WORKSPACE_ROOT}"

# Default Configuration
IMAGE="docker.io/library/debian:13-slim"
NETWORK_MODE="none"
MEMORY_LIMIT="2g"
CPU_LIMIT="2"
READ_ONLY=false
DRY_RUN=false
TARGET_DIR="${PWD}"

show_help() {
    cat <<HELP
Usage: $(basename "$0") [OPTIONS] [-- <command...>]

Execute untrusted subagent tasks in a hardened rootless container sandbox.

Options:
  --image <image>        Base container image (default: "docker.io/library/debian:13-slim")
  --network <mode>       Network mode: none | slirp4netns | host (default: "none")
  --mem <limit>          Memory limit with unit (default: "2g")
  --cpus <count>         Allocated virtual CPU cores (default: "2")
  --read-only            Mount workspace directory as read-only volume
  --target-dir <path>    Workspace path to mount (default: current working directory)
  --dry-run              Print constructed podman command without executing
  -h, --help             Show this help message and exit

Security Invariants:
  - Target directory must reside strictly under /home/rizz/dev/
  - Container root filesystem is mounted --read-only
  - Linux capabilities dropped via --cap-drop=ALL
  - Enforces --security-opt=no-new-privileges and --pids-limit=256
  - User namespace UID mapping preserved via --userns=keep-id
HELP
}

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
        --target-dir)
            TARGET_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        --)
            shift
            COMMAND_ARGS=("$@")
            break
            ;;
        *)
            if [ -z "${COMMAND_ARGS[*]:-}" ]; then
                COMMAND_ARGS=("$@")
                break
            fi
            ;;
    esac
done

# Validate Target Workspace Boundary: strictly under /home/rizz/dev/
CANONICAL_TARGET="$(realpath -m "${TARGET_DIR}" 2>/dev/null || echo "${TARGET_DIR}")"
if [[ ! "${CANONICAL_TARGET}" =~ ^/home/rizz/dev(/|$) ]]; then
    echo "[SECURITY ERROR] Sandbox target directory must reside strictly under /home/rizz/dev/: ${TARGET_DIR}" >&2
    exit 2
fi

if [ ${#COMMAND_ARGS[@]} -eq 0 ] && [ "${DRY_RUN}" = false ]; then
    echo "Error: No command specified to execute." >&2
    show_help >&2
    exit 1
fi

# Determine Mount Permissions
MOUNT_MODE="rw"
if [ "${READ_ONLY}" = true ]; then
    MOUNT_MODE="ro"
fi

# Assemble Podman Command
PODMAN_CMD=(
    podman run
    --rm
    -i
    --read-only
    --userns=keep-id
    --network="${NETWORK_MODE}"
    --memory="${MEMORY_LIMIT}"
    --cpus="${CPU_LIMIT}"
    --pids-limit=256
    --cap-drop=ALL
    --security-opt=no-new-privileges
    -v "${CANONICAL_TARGET}:/workspace:${MOUNT_MODE},z"
    -w /workspace
    "${IMAGE}"
    "${COMMAND_ARGS[@]}"
)

if [ "${DRY_RUN}" = true ]; then
    echo "${PODMAN_CMD[*]}"
    exit 0
fi

# Verify Podman Availability
if ! command -v podman >/dev/null 2>&1; then
    echo "[ERROR] Podman is not installed. Install via your package manager (e.g., sudo apt install -y podman)" >&2
    exit 1
fi

# Execute Command in Sandbox Container
"${PODMAN_CMD[@]}"
