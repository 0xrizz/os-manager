#!/usr/bin/env bash
# ==============================================================================
# sys_diag.sh - Unified System & Environment Diagnostics (Cross-Distribution)
# ==============================================================================
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source Distribution Engine
if [ -f "${WORKSPACE_ROOT}/scripts/lib/distro.sh" ]; then
    # shellcheck source=scripts/lib/distro.sh
    source "${WORKSPACE_ROOT}/scripts/lib/distro.sh"
fi

echo "=============================================================================="
echo "                   SYSTEM & ENVIRONMENT DIAGNOSTICS"
echo "=============================================================================="

echo "==> [1/6] Kernel & OS Identification:"
uname -a
echo "Distribution Family : ${OS_DISTRO_FAMILY:-unknown}"
echo "Distribution Name   : ${OS_DISTRO_NAME:-Linux}"
echo "Package Manager     : ${OS_PKG_MANAGER:-unknown}"

echo -e "\n==> [2/6] Memory & Resource Usage:"
free -h

echo -e "\n==> [3/6] Disk Allocations & File Systems:"
df -h / /mnt/c /mnt/d 2>/dev/null || df -h /

echo -e "\n==> [4/6] Systemd & Service Health:"
if command -v systemctl &>/dev/null; then
    echo "System state: $(systemctl is-system-running 2>&1 || true)"
    FAILED_UNITS=$(systemctl --failed --no-legend 2>&1 || true)
    if [ -z "$FAILED_UNITS" ]; then
        echo "Failed units: None (all healthy)"
    else
        echo "Failed units:"
        echo "$FAILED_UNITS"
    fi
fi

echo -e "\n==> [5/6] Network & Interop Connectivity:"
if ping -c 1 -W 2 1.1.1.1 &>/dev/null; then
    echo "Internet reachability: OK (1.1.1.1 reachable)"
else
    echo "Internet reachability: WARNING (Unable to ping 1.1.1.1)"
fi

echo -e "\n==> [6/6] Developer Toolchains:"
for tool in node pnpm bun uv agy claude wrangler git tmux; do
    if command -v "$tool" &>/dev/null; then
        printf "%-12s: %s (%s)\n" "$tool" "INSTALLED" "$(command -v "$tool")"
    else
        printf "%-12s: %s\n" "$tool" "NOT FOUND"
    fi
done

echo "=============================================================================="
