#!/usr/bin/env bash
# ==============================================================================
# update_runtimes.sh - Update Runtimes, Toolchains, and Package Repositories
# ==============================================================================
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source Distribution Engine if present
if [ -f "${WORKSPACE_ROOT}/scripts/lib/distro.sh" ]; then
    # shellcheck source=scripts/lib/distro.sh
    source "${WORKSPACE_ROOT}/scripts/lib/distro.sh"
fi

echo "==> [1/3] Updating system package repositories (${OS_DISTRO_NAME:-Linux})..."
if declare -F pkg_update >/dev/null 2>&1 && declare -F pkg_upgrade >/dev/null 2>&1; then
    pkg_update "$@" || true
    pkg_upgrade "$@" || true
elif command -v apt-get &>/dev/null; then
    if [ -x "${WORKSPACE_ROOT}/scripts/sudo_exec.sh" ]; then
        "${WORKSPACE_ROOT}/scripts/sudo_exec.sh" apt-get update && "${WORKSPACE_ROOT}/scripts/sudo_exec.sh" apt-get upgrade -y
    fi
fi

echo "==> [2/3] Updating mise declarative toolchains..."
MISE_BIN="$(command -v mise 2>/dev/null || echo "${HOME}/.local/bin/mise")"
if [ -x "${MISE_BIN}" ]; then
    echo "Updating mise binary..."
    "${MISE_BIN}" self-update 2>/dev/null || true
    echo "Upgrading managed toolchains..."
    "${MISE_BIN}" upgrade || true
    echo "Pruning stale versions..."
    "${MISE_BIN}" prune -y || true
else
    echo "Warning: mise binary not found at ${MISE_BIN}" >&2
fi

echo "==> [3/3] Updating Astral UV and user-space tools..."
UV_BIN="$(command -v uv 2>/dev/null || echo "${HOME}/.local/bin/uv")"
if [ -x "${UV_BIN}" ]; then
    "${UV_BIN}" self update 2>/dev/null || true
    "${UV_BIN}" tool upgrade --all 2>/dev/null || true
fi

echo "All runtimes updated."
