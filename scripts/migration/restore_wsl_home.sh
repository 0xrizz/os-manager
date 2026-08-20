#!/usr/bin/env bash
# scripts/migration/restore_wsl_home.sh - Phase 4 WSL Home Environment & Dotfiles Restoration
# Extracts WSL backup archive into target home directory and enforces strict SSH permissions
set -euo pipefail

BACKUP_ARCHIVE="/mnt/data/wsl_backup/wsl_home_backup.tar.gz"
TARGET_DIR="${HOME}"
DRY_RUN=false

show_help() {
    cat << 'EOF'
Usage: restore_wsl_home.sh [options]

Phase 4 WSL home restoration script for Debian bare-metal migration.
Restores dotfiles, SSH keys, git configurations, and development workspaces
from the WSL tarball backup archive to the target user home directory.

Options:
  -a, --archive <path> Path to WSL home backup archive (default: /mnt/data/wsl_backup/wsl_home_backup.tar.gz)
  -t, --target <path>  Target home directory destination (default: $HOME)
  -d, --dry-run        Simulate extraction and display archive contents without modifying files
  -h, --help           Show this help message and exit

Examples:
  ./scripts/migration/restore_wsl_home.sh
  ./scripts/migration/restore_wsl_home.sh --dry-run
  ./scripts/migration/restore_wsl_home.sh --archive /custom/path/backup.tar.gz --target /home/user
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -a|--archive)
            if [[ -z "${2:-}" ]]; then
                echo "ERROR: --archive requires a file path argument." >&2
                exit 1
            fi
            BACKUP_ARCHIVE="$2"
            shift 2
            ;;
        -t|--target)
            if [[ -z "${2:-}" ]]; then
                echo "ERROR: --target requires a directory path argument." >&2
                exit 1
            fi
            TARGET_DIR="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option '$1'. Use --help for usage details." >&2
            exit 1
            ;;
    esac
done

echo "=================================================="
echo " Phase 4: WSL Home Environment Restoration"
echo "=================================================="
echo "Backup Archive : ${BACKUP_ARCHIVE}"
echo "Target Directory: ${TARGET_DIR}"

# 1. Validate Archive File
if [[ ! -f "${BACKUP_ARCHIVE}" ]]; then
    echo "ERROR: Backup archive '${BACKUP_ARCHIVE}' not found or is not a regular file." >&2
    echo "Please ensure Partition 4 is mounted at /mnt/data or pass --archive <path>." >&2
    exit 1
fi

if [[ ! -s "${BACKUP_ARCHIVE}" ]]; then
    echo "ERROR: Backup archive '${BACKUP_ARCHIVE}' is empty (0 bytes)." >&2
    exit 1
fi

# 2. Dry Run Simulation Mode
if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Simulating WSL home extraction to ${TARGET_DIR}..."
    echo "[DRY RUN] Inspecting archive contents (first 25 entries):"
    tar -ztvf "${BACKUP_ARCHIVE}" | head -n 25 || true
    echo "[DRY RUN] Would extract all files into: ${TARGET_DIR}"
    echo "[DRY RUN] Would enforce SSH key permissions:"
    echo "          chmod 700 ${TARGET_DIR}/.ssh"
    echo "          chmod 600 ${TARGET_DIR}/.ssh/* (private keys, config)"
    echo "          chmod 644 ${TARGET_DIR}/.ssh/*.pub (public keys)"
    echo "=================================================="
    echo "[DRY RUN] Simulation finished successfully."
    echo "=================================================="
    exit 0
fi

# 3. Live Archive Extraction
echo "Ensuring target directory exists: ${TARGET_DIR}"
mkdir -p "${TARGET_DIR}"

echo "Extracting dotfiles, SSH keys, configs, and workspace repositories to ${TARGET_DIR}..."
tar -xzvf "${BACKUP_ARCHIVE}" -C "${TARGET_DIR}"

# 4. Enforce Strict SSH Key Permissions
SSH_DIR="${TARGET_DIR}/.ssh"
if [[ -d "${SSH_DIR}" ]]; then
    echo "Securing SSH key permissions in ${SSH_DIR}..."
    chmod 700 "${SSH_DIR}"
    
    # Set private keys and config files to 600
    chmod 600 "${SSH_DIR}"/* 2>/dev/null || true
    
    # Set public keys to 644
    chmod 644 "${SSH_DIR}"/*.pub 2>/dev/null || true
    
    # Set known_hosts and config if present
    if [[ -f "${SSH_DIR}/known_hosts" ]]; then
        chmod 644 "${SSH_DIR}/known_hosts" 2>/dev/null || true
    fi
    if [[ -f "${SSH_DIR}/config" ]]; then
        chmod 600 "${SSH_DIR}/config" 2>/dev/null || true
    fi
    if [[ -f "${SSH_DIR}/authorized_keys" ]]; then
        chmod 600 "${SSH_DIR}/authorized_keys" 2>/dev/null || true
    fi
    echo "SSH permissions secured (dir: 700, keys/configs: 600, pub/known_hosts: 644)."
fi

echo "=================================================="
echo "SUCCESS: WSL environment restored successfully."
echo "=================================================="
