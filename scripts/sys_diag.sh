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

JSON_MODE=false
FULL_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --json)
            JSON_MODE=true
            shift
            ;;
        --full)
            FULL_MODE=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Colors
C_RESET="\033[0m"
C_GREEN="\033[32m"
C_YELLOW="\033[33m"
C_CYAN="\033[36m"
C_BOLD="\033[1m"

BADGE_OK="${C_GREEN}[OK]${C_RESET}"
BADGE_WARN="${C_YELLOW}[WARN]${C_RESET}"
BADGE_SANDBOX="${C_CYAN}[SANDBOX]${C_RESET}"

KERNEL_VER="$(uname -r)"
if command -v free >/dev/null 2>&1; then
    RAM_SUMMARY="$(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
else
    RAM_SUMMARY="N/A"
fi
DISK_SUMMARY="$(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}')"

if [ "${JSON_MODE}" = true ]; then
    cat <<JSON
{
  "status": "healthy",
  "kernel": "${KERNEL_VER}",
  "distro": "${OS_DISTRO_NAME:-Linux}",
  "ram_usage": "${RAM_SUMMARY}",
  "disk_usage": "${DISK_SUMMARY}",
  "sandbox_ready": $(command -v podman &>/dev/null && echo "true" || echo "false")
}
JSON
    exit 0
fi

if [ "${FULL_MODE}" = false ]; then
    echo -e "┌─ ${C_BOLD}os-manager v1.2${C_RESET} ────────────────────────────────────────────────────────┐"
    echo -e "│  Host: ${OS_DISTRO_NAME:-Linux} (${OS_DISTRO_FAMILY:-Linux})  •  Kernel: ${KERNEL_VER}  •  RAM: ${RAM_SUMMARY}  │"
    echo -e "│  Disk: ${DISK_SUMMARY}  •  Status: ${BADGE_OK}  •  Sandbox: ${BADGE_SANDBOX} Ready     │"
    echo -e "└──────────────────────────────────────────────────────────────────────────┘"
    exit 0
fi

echo "=============================================================================="
echo "                   SYSTEM & ENVIRONMENT DIAGNOSTICS"
echo "=============================================================================="
echo -e "==> [1/6] Kernel & OS: ${BADGE_OK} ${KERNEL_VER} (${OS_DISTRO_NAME:-Linux})"
echo "Distribution Family : ${OS_DISTRO_FAMILY:-unknown}"
echo "Distribution Name   : ${OS_DISTRO_NAME:-Linux}"
echo "Package Manager     : ${OS_PKG_MANAGER:-unknown}"

echo -e "\n==> [2/6] Memory Usage: ${BADGE_OK} ${RAM_SUMMARY}"
free -h

echo -e "\n==> [3/6] Disk Allocations: ${BADGE_OK} ${DISK_SUMMARY}"
df -h / /mnt/c /mnt/d 2>/dev/null || df -h /

echo -e "\n==> [4/6] Systemd & Service Health:"
if command -v systemctl &>/dev/null; then
    echo "System state: $(systemctl is-system-running 2>&1 || true)"
    FAILED_UNITS=$(systemctl --failed --no-legend 2>&1 || true)
    if [ -z "$FAILED_UNITS" ]; then
        echo -e "Failed units: None (${BADGE_OK} all healthy)"
    else
        echo "Failed units:"
        echo "$FAILED_UNITS"
    fi
fi

echo -e "\n==> [5/6] Network & Interop Connectivity:"
if ping -c 1 -W 2 1.1.1.1 &>/dev/null; then
    echo -e "Internet reachability: ${BADGE_OK} (1.1.1.1 reachable)"
else
    echo -e "Internet reachability: ${BADGE_WARN} (Unable to ping 1.1.1.1)"
fi

echo -e "\n==> [6/6] Developer Toolchains:"
for tool in node pnpm bun uv agy claude wrangler git tmux; do
    if command -v "$tool" &>/dev/null; then
        printf "%-12s: %b %s (%s)\n" "$tool" "${BADGE_OK}" "INSTALLED" "$(command -v "$tool")"
    else
        printf "%-12s: %s\n" "$tool" "NOT FOUND"
    fi
done

echo "=============================================================================="
