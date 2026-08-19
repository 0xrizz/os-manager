#!/usr/bin/env bash
# ==============================================================================
# Repository Migration Utility (Windows NTFS /mnt/d/dev -> Native ext4 developer root)
# ==============================================================================
set -euo pipefail

SOURCE_BASE="/mnt/d/dev"
DEST_BASE="${OSM_DEV_ROOT:-${HOME}/dev}"

REPOS=(
  "agy-os"
  "agy-research"
  "agy-root"
  "arostech-hub"
  "ECC"
  "logs_81993939307"
  "openspec"
  "agy-harness"
)

echo "=================================================="
echo " Starting Repository Migration to Native ext4     "
echo "=================================================="
mkdir -p "$DEST_BASE"

for repo in "${REPOS[@]}"; do
  src="${SOURCE_BASE}/${repo}"
  dst="${DEST_BASE}/${repo}"

  if [ -d "$src" ]; then
    echo "==> [Syncing] $repo -> $dst"
    mkdir -p "$dst"
    rsync -a --info=progress2 \
      --exclude="node_modules" \
      --exclude=".next" \
      --exclude=".venv" \
      --exclude="venv" \
      --exclude="__pycache__" \
      --exclude="*.pyc" \
      --exclude="dist" \
      --exclude="build" \
      --exclude="target" \
      --exclude="coverage" \
      --exclude=".turbo" \
      --exclude=".cache" \
      --exclude="*.swc" \
      --exclude="*.node" \
      --exclude=".git/gc.log" \
      --exclude=".git/index.lock" \
      "${src}/" "${dst}/"
    echo "    ✓ Completed: $repo"
  else
    echo "    ⚠ Skipping: $src (Directory not found)"
  fi
done

echo "=================================================="
echo " All repositories synchronized successfully.      "
echo "=================================================="
