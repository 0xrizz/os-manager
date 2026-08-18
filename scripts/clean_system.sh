#!/usr/bin/env bash
# ==============================================================================
# clean_system.sh — Safe Storage, Package & Runtime Cleaner
# ==============================================================================
set -euo pipefail

echo "==> [1/4] Cleaning APT caches & orphan packages..."
sudo apt autoremove -y
sudo apt clean

echo "==> [2/4] Cleaning Python UV tool caches..."
if command -v uv &>/dev/null; then
  uv cache clean || true
fi

echo "==> [3/4] Cleaning PNPM global store & corrupted temp caches..."
if command -v pnpm &>/dev/null; then
  pnpm store prune || true
fi
rm -rf "$HOME/.cache/puppeteer"

echo "==> [4/4] Reporting available space:"
df -h /
echo "Cleanup completed safely."
