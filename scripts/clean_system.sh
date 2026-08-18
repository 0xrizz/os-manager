#!/usr/bin/env bash
# ==============================================================================
# clean_system.sh - Safe Storage, Package & Runtime Cleaner (Cross-Distribution)
# ==============================================================================
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source Distribution Engine
if [ -f "${WORKSPACE_ROOT}/scripts/lib/distro.sh" ]; then
    # shellcheck source=scripts/lib/distro.sh
    source "${WORKSPACE_ROOT}/scripts/lib/distro.sh"
fi

COMPACT_MODE=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --compact|--all)
            COMPACT_MODE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

if [ "${DRY_RUN}" = true ]; then
    echo "==> [DRY RUN] Simulating package and runtime cache cleanups for: ${OS_DISTRO_NAME:-Linux}"
    exit 0
fi

echo "==> [1/4] Cleaning system package caches (${OS_DISTRO_NAME:-Linux})..."
if declare -F pkg_clean >/dev/null 2>&1; then
    pkg_clean || true
elif command -v apt &>/dev/null; then
    sudo apt autoremove -y && sudo apt clean
fi

echo "==> [2/4] Cleaning Python UV tool caches..."
if command -v uv &>/dev/null; then
    uv cache clean || true
fi

echo "==> [3/4] Cleaning PNPM global store & corrupted temp caches..."
if command -v pnpm &>/dev/null; then
    pnpm store prune || true
fi
rm -rf "${HOME}/.cache/puppeteer" 2>/dev/null || true

# Optional: Run compaction if requested
if [ "${COMPACT_MODE}" = true ] && [ -x "${WORKSPACE_ROOT}/scripts/compact_host_disk.sh" ]; then
    echo "==> Triggering host disk compaction..."
    "${WORKSPACE_ROOT}/scripts/compact_host_disk.sh" || true
fi

echo "==> [4/4] Reporting available space:"
df -h /
echo "Cleanup completed safely."
