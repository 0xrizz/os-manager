#!/usr/bin/env bash
# scripts/dotfiles_sync.sh - Dotfile backup, diff, and template synchronization
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
                cp -v "${HOME}/${f}" "${BACKUP_TARGET}/${f}.example"
            fi
        done
        echo "Backup complete in ${BACKUP_TARGET}"
        ;;
    diff)
        echo "=== Dotfiles Diff Inspection ==="
        for f in "${FILES_TO_MANAGE[@]}"; do
            local_src="${BACKUP_TARGET}/${f}"
            [ ! -f "${local_src}" ] && local_src="${BACKUP_TARGET}/${f}.example"

            if [ -f "${local_src}" ] && [ -f "${HOME}/${f}" ]; then
                echo "--- Diff for ~/${f} (against ${local_src}) ---"
                diff -u "${local_src}" "${HOME}/${f}" || true
            elif [ -f "${HOME}/${f}" ]; then
                echo "File ~/${f} exists but has no template in repository."
            fi
        done
        ;;
    restore)
        echo "=== Restoring Dotfiles ==="
        for f in "${FILES_TO_MANAGE[@]}"; do
            local_src="${BACKUP_TARGET}/${f}"
            [ ! -f "${local_src}" ] && local_src="${BACKUP_TARGET}/${f}.example"

            if [ -f "${local_src}" ]; then
                cp -iv "${local_src}" "${HOME}/${f}"
            fi
        done
        ;;
    *)
        echo "Usage: $0 {backup|diff|restore}"
        exit 1
        ;;
esac
