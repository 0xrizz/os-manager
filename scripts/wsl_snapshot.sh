#!/usr/bin/env bash
# ==============================================================================
# wsl_snapshot.sh — Backup and Export WSL Debian Distro
# ==============================================================================
set -euo pipefail

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
echo "To restore from this snapshot if disaster occurs:"
echo "  wsl --import Debian-Restored \"C:\\WSL\\Debian\" \"D:\\wsl_backup\\debian_snapshot_${DATE_TAG}.tar\""
echo "=============================================================================="
