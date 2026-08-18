#!/usr/bin/env bash
# ==============================================================================
# update_runtimes.sh — Update Node, NVM, PNPM, Bun, UV, and Global CLIs
# ==============================================================================
set -euo pipefail

echo "==> [1/5] Updating APT package repositories..."
sudo apt update && sudo apt upgrade -y

echo "==> [2/5] Updating Node / NVM toolchains..."
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
corepack prepare pnpm@latest --activate || true

echo "==> [3/5] Updating Bun runtime..."
if command -v bun &>/dev/null; then
  bun upgrade || true
fi

echo "==> [4/5] Updating Astral UV..."
if command -v uv &>/dev/null; then
  uv self update || true
fi

echo "==> [5/5] Updating AI Coding and Cloudflare CLIs..."
npm install -g @anthropic-ai/claude-code --allow-scripts || true
npm install -g wrangler --allow-scripts || true
if command -v agy &>/dev/null; then
  curl -fsSL https://antigravity.google/cli/install.sh | bash || true
fi

echo "All runtimes updated."
