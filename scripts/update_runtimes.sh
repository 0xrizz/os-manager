#!/usr/bin/env bash
# ==============================================================================
# update_runtimes.sh - Update Runtimes, Toolchains, and Package Repositories
# ==============================================================================
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source Distribution Engine
if [ -f "${WORKSPACE_ROOT}/scripts/lib/distro.sh" ]; then
    # shellcheck source=scripts/lib/distro.sh
    source "${WORKSPACE_ROOT}/scripts/lib/distro.sh"
fi

echo "==> [1/5] Updating system package repositories (${OS_DISTRO_NAME:-Linux})..."
if declare -F pkg_update >/dev/null 2>&1 && declare -F pkg_upgrade >/dev/null 2>&1; then
    pkg_update "$@" || true
    pkg_upgrade "$@" || true
elif command -v apt &>/dev/null; then
    sudo apt update && sudo apt upgrade -y
fi

echo "==> [2/5] Updating Node / NVM toolchains..."
export NVM_DIR="${HOME}/.nvm"
if [ -s "${NVM_DIR}/nvm.sh" ]; then
    # shellcheck disable=SC1090,SC1091
    source "${NVM_DIR}/nvm.sh"
fi
if command -v corepack &>/dev/null; then
    corepack enable pnpm yarn 2>/dev/null || true
    corepack prepare pnpm@latest --activate 2>/dev/null || true
fi

echo "==> [3/5] Updating Bun runtime..."
if command -v bun &>/dev/null; then
    bun upgrade 2>/dev/null || true
fi

echo "==> [4/5] Updating Astral UV..."
if command -v uv &>/dev/null; then
    uv self update 2>/dev/null || true
fi

echo "==> [5/5] Updating AI Coding and Developer CLIs..."
if command -v claude &>/dev/null || [ -f "${HOME}/.local/bin/claude" ]; then
    curl -fsSL https://claude.ai/install.sh | bash 2>/dev/null || true
fi
if command -v npm &>/dev/null; then
    npm install -g --allow-scripts=wrangler wrangler 2>/dev/null || true
fi
if command -v agy &>/dev/null; then
    curl -fsSL https://antigravity.google/cli/install.sh | bash 2>/dev/null || true
fi
if command -v gh &>/dev/null; then
    if command -v apt &>/dev/null; then
        sudo apt update && sudo apt install -y --only-upgrade gh 2>/dev/null || true
    fi
fi

echo "All runtimes updated."
