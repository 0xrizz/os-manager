#!/usr/bin/env bash
# tests/test_backup_redundancy.sh - Validates GPT Partition & BCD Redundancy Backup
# Ensures disk_layout.json, partition_layout.json, bcd_backup.bcd, and wsl_home_backup integrity on Drive D:
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/mnt/d}"
WSL_BACKUP_DIR="${WSL_BACKUP_DIR:-/mnt/d/wsl_backup}"

echo "=================================================="
echo "Verifying Redundancy Backup Artifacts on Drive D:"
echo "=================================================="

echo "Checking required backup files exist and are non-empty..."
test -s "${BACKUP_DIR}/disk_layout.json" || { echo "FAIL: disk_layout.json missing or empty at ${BACKUP_DIR}"; exit 1; }
echo "  [PASS] ${BACKUP_DIR}/disk_layout.json present ($(stat -c %s "${BACKUP_DIR}/disk_layout.json") bytes)"

test -s "${BACKUP_DIR}/partition_layout.json" || { echo "FAIL: partition_layout.json missing or empty at ${BACKUP_DIR}"; exit 1; }
echo "  [PASS] ${BACKUP_DIR}/partition_layout.json present ($(stat -c %s "${BACKUP_DIR}/partition_layout.json") bytes)"

test -s "${BACKUP_DIR}/bcd_backup.bcd" || { echo "FAIL: bcd_backup.bcd missing or empty at ${BACKUP_DIR}"; exit 1; }
echo "  [PASS] ${BACKUP_DIR}/bcd_backup.bcd present ($(stat -c %s "${BACKUP_DIR}/bcd_backup.bcd") bytes)"

test -s "${WSL_BACKUP_DIR}/wsl_home_backup.tar.gz" || { echo "FAIL: wsl_home_backup.tar.gz missing at ${WSL_BACKUP_DIR}"; exit 1; }
echo "  [PASS] ${WSL_BACKUP_DIR}/wsl_home_backup.tar.gz present ($(stat -c %s "${WSL_BACKUP_DIR}/wsl_home_backup.tar.gz") bytes)"

test -s "${WSL_BACKUP_DIR}/wsl_home_backup.sha256" || { echo "FAIL: wsl_home_backup.sha256 missing at ${WSL_BACKUP_DIR}"; exit 1; }
echo "  [PASS] ${WSL_BACKUP_DIR}/wsl_home_backup.sha256 present"

echo ""
echo "Verifying WSL home archive SHA256 checksum match..."
(
    cd "$WSL_BACKUP_DIR"
    sha256sum -c wsl_home_backup.sha256
)

echo ""
echo "=================================================="
echo "PASS: All redundancy backups are present, non-empty, and checksum-verified."
echo "=================================================="
