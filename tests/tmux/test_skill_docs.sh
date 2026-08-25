#!/usr/bin/env bash
set -euo pipefail

SKILL_FILE=".claude/skills/tmux-agents/SKILL.md"

echo "==> Checking skill documentation content..."
if ! grep -q "company" "$SKILL_FILE"; then
  echo "FAIL: SKILL.md missing 'company' mode documentation"
  exit 1
fi

if ! grep -q "worktree" "$SKILL_FILE"; then
  echo "FAIL: SKILL.md missing 'worktree' documentation"
  exit 1
fi

if ! grep -q "capture" "$SKILL_FILE"; then
  echo "FAIL: SKILL.md missing 'capture' documentation"
  exit 1
fi

echo "PASS: Skill documentation verified."
