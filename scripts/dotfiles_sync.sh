#!/usr/bin/env bash
# scripts/dotfiles_sync.sh - Pillar 4 State Protection & Dotfile Diff/Sync
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_TARGET="${WORKSPACE_ROOT}/backups/dotfiles"
mkdir -p "${BACKUP_TARGET}"

ACTION="${1:-diff}"

FILES_TO_MANAGE=(
    ".bashrc"
    ".tmux.conf"
    ".gitconfig"
)

case "${ACTION}" in
    backup)
        echo "=== Backing up Dotfiles ==="
        for f in "${FILES_TO_MANAGE[@]}"; do
            if [ -f "${HOME}/${f}" ]; then
                cp -v "${HOME}/${f}" "${BACKUP_TARGET}/${f}"
            fi
        done
        echo "Backup complete in ${BACKUP_TARGET}"
        ;;
    diff)
        echo "=== Dotfiles Diff Inspection ==="
        for f in "${FILES_TO_MANAGE[@]}"; do
            if [ -f "${BACKUP_TARGET}/${f}" ] && [ -f "${HOME}/${f}" ]; then
                echo "--- Diff for ~/${f} ---"
                diff -u "${BACKUP_TARGET}/${f}" "${HOME}/${f}" || true
            elif [ -f "${HOME}/${f}" ]; then
                echo "File ~/${f} exists but has no backup in repository."
            fi
        done
        ;;
    restore)
        echo "=== Restoring Dotfiles ==="
        for f in "${FILES_TO_MANAGE[@]}"; do
            if [ -f "${BACKUP_TARGET}/${f}" ]; then
                cp -iv "${BACKUP_TARGET}/${f}" "${HOME}/${f}"
            fi
        done
        ;;
    *)
        echo "Usage: $0 {backup|diff|restore}"
        exit 1
        ;;
esac
