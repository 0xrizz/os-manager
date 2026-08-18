#!/usr/bin/env bash
# ==============================================================================
# wsl_snapshot.sh — Backup and Export WSL Debian Distro
# ==============================================================================
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="/mnt/d/wsl_backup"
DATE_TAG=$(date +"%Y%m%d_%H%M%S")
SNAPSHOT_FILE="$BACKUP_DIR/debian_snapshot_${DATE_TAG}.tar"

echo "==> Creating backup directory at $BACKUP_DIR (if not exists)..."
mkdir -p "$BACKUP_DIR"

echo "=============================================================================="
echo " WSL BACKUP HELPER"
echo "=============================================================================="
echo "To create a complete snapshot of this Debian instance, execute the following"
echo "command from Windows PowerShell / Terminal:"
echo ""
echo "  wsl --export Debian \"D:\\wsl_backup\\debian_snapshot_${DATE_TAG}.tar\""
echo ""
echo "Target snapshot path: ${SNAPSHOT_FILE}"
echo "To restore from this snapshot if disaster occurs:"
echo "  wsl --import Debian-Restored \"C:\\WSL\\Debian\" \"D:\\wsl_backup\\debian_snapshot_${DATE_TAG}.tar\""
echo "=============================================================================="

# Dispatch desktop notification helper
NOTIFIER="${WORKSPACE_ROOT}/scripts/notify_host.sh"
if [ -x "${NOTIFIER}" ]; then
    "${NOTIFIER}" --type info --title "WSL Snapshot Ready" --message "Export target prepared: debian_snapshot_${DATE_TAG}.tar" --async 2>/dev/null || true
fi
