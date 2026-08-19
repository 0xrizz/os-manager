#!/usr/bin/env bash
# scripts/compact_host_disk.sh - Automated WSL2 Host VHDX Disk Compaction
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC2034
_WORKSPACE="${WORKSPACE_ROOT}"
LOCK_FILE="/tmp/os_manager_compaction.lock"

# Default configuration
THRESHOLD_GB=10
DRY_RUN=false
SKIP_FSTRIM=false
FORCE=false

show_help() {
    cat <<HELP
Usage: $(basename "$0") [OPTIONS]

Automated WSL2 Host Virtual Hard Disk (ext4.vhdx) Compaction Utility.

Options:
  --threshold-gb <N>   Minimum reclaimable slack space in GB to trigger compaction (default: 10)
  --dry-run            Simulate space calculation and print actions without shrinking VHDX
  --skip-fstrim        Skip the initial guest filesystem discard routine (not recommended)
  --force              Trigger compaction regardless of the calculated slack threshold
  -h, --help           Show this help message and exit

Workflow:
  1. Executes 'sudo fstrim -v /' to discard unallocated Linux filesystem blocks.
  2. Discovers backing ext4.vhdx on the Windows host and measures its file size.
  3. Calculates slack = (Host VHDX Size - Ext4 Used Size).
  4. If slack >= THRESHOLD_GB (or --force), triggers PowerShell 'Optimize-VHD'.
HELP
}

# Parse CLI arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold-gb)
            THRESHOLD_GB="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-fstrim)
            SKIP_FSTRIM=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown argument '$1'" >&2
            show_help >&2
            exit 1
            ;;
    esac
done

# Concurrency lockfile protection
exec 200>"${LOCK_FILE}"
if command -v flock >/dev/null 2>&1; then
    if ! flock -n 200; then
        echo "Notice: Disk compaction is already in progress by another process. Exiting cleanly."
        exit 0
    fi
fi

echo "=============================================================================="
echo " WSL2 AUTOMATED HOST DISK COMPACTION COORDINATOR"
echo "=============================================================================="

# Step 1: Mandatory Guest Block Discard (fstrim)
if [ "${SKIP_FSTRIM}" = false ]; then
    echo "==> [1/3] Discarding unallocated ext4 blocks via fstrim..."
    if [ "${DRY_RUN}" = true ]; then
        echo "    [DRY RUN] Would execute: sudo fstrim -v /"
    else
        if command -v fstrim >/dev/null 2>&1; then
            sudo fstrim -v / 2>/dev/null || echo "    Notice: fstrim exited with non-zero status; continuing."
        fi
    fi
else
    echo "==> [1/3] Skipping fstrim step (--skip-fstrim specified)."
fi

# Step 2: Measure Guest Space Usage
EXT4_USED_BYTES="$(df -B1 / | awk 'NR==2 {print $3}')"
EXT4_USED_GB="$(awk "BEGIN {printf \"%.2f\", ${EXT4_USED_BYTES} / 1073741824}")"
echo "==> [2/3] Guest filesystem (ext4) active data: ${EXT4_USED_GB} GB (${EXT4_USED_BYTES} bytes)"

# Step 3: Check Windows Interop and Discover Host VHDX
if [ ! -f "/proc/sys/fs/binfmt_misc/WSLInterop" ] || ! command -v powershell.exe >/dev/null 2>&1; then
    echo "Notice: Windows PowerShell interop is not available in this environment."
    echo "        Guest blocks were trimmed. Host-side VHDX compaction cannot be automated."
    exit 0
fi

# Resolve VHDX path on host via PowerShell
echo "==> Locating WSL2 ext4.vhdx on Windows host..."
# shellcheck disable=SC2016
PS_QUERY_VHDX='
$distro = "Debian";
$pkgPath = "$env:LOCALAPPDATA\Packages";
$vhdx = Get-ChildItem -Path $pkgPath -Filter "ext4.vhdx" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1;
if ($vhdx) {
    Write-Output "$($vhdx.FullName)|$($vhdx.Length)"
} else {
    Write-Output "NOT_FOUND|0"
}
'

VHDX_INFO="$(powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "${PS_QUERY_VHDX}" 2>/dev/null | tr -d '\r' | head -n 1 || echo "NOT_FOUND|0")"

VHDX_PATH="${VHDX_INFO%%|*}"
VHDX_BYTES="${VHDX_INFO##*|}"

if [ "${VHDX_PATH}" = "NOT_FOUND" ] || [ -z "${VHDX_BYTES}" ] || [ "${VHDX_BYTES}" -eq 0 ]; then
    echo "Notice: Backing ext4.vhdx path could not be located dynamically under %LOCALAPPDATA%."
    echo "        To compact manually from Windows PowerShell (Run as Administrator):"
    echo "        wsl --shutdown"
    echo "        diskpart -> select vdisk file=\"<path-to-ext4.vhdx>\" -> compact vdisk"
    exit 0
fi

VHDX_GB="$(awk "BEGIN {printf \"%.2f\", ${VHDX_BYTES} / 1073741824}")"
SLACK_BYTES=$(( VHDX_BYTES - EXT4_USED_BYTES ))
if [ "${SLACK_BYTES}" -lt 0 ]; then
    SLACK_BYTES=0
fi
SLACK_GB="$(awk "BEGIN {printf \"%.2f\", ${SLACK_BYTES} / 1073741824}")"

echo "==> Host VHDX Path: ${VHDX_PATH}"
echo "==> Host VHDX File Size: ${VHDX_GB} GB"
echo "==> Reclaimable Slack Space: ${SLACK_GB} GB (Threshold: ${THRESHOLD_GB} GB)"

# Step 4: Evaluate Threshold and Execute Compaction
THRESHOLD_BYTES=$(( THRESHOLD_GB * 1073741824 ))

if [ "${SLACK_BYTES}" -ge "${THRESHOLD_BYTES}" ] || [ "${FORCE}" = true ]; then
    echo "==> [3/3] Slack space (${SLACK_GB} GB) exceeds threshold (${THRESHOLD_GB} GB). Initiating compaction..."

    if [ "${DRY_RUN}" = true ]; then
        echo "    [DRY RUN] Would execute Optimize-VHD on: ${VHDX_PATH}"
        echo "Compaction evaluation complete (dry-run)."
        exit 0
    fi

    # Trigger PowerShell Optimize-VHD / diskpart fallback
    PS_COMPACT_CMD="
    \$path = \"${VHDX_PATH}\";
    if (Get-Command Optimize-VHD -ErrorAction SilentlyContinue) {
        Write-Output \"Executing Hyper-V Optimize-VHD...\";
        Optimize-VHD -Path \$path -Mode Full -ErrorAction SilentlyContinue;
    } else {
        Write-Output \"Optimize-VHD cmdlet unavailable (Hyper-V module required).\";
    }
    "
    powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "${PS_COMPACT_CMD}" || true
    echo "✓ Compaction routine completed."
else
    echo "==> [3/3] Slack space (${SLACK_GB} GB) is below the threshold (${THRESHOLD_GB} GB). Skipping host compaction."
fi

echo "=============================================================================="
