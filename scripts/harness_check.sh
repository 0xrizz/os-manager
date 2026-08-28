#!/usr/bin/env bash
# scripts/harness_check.sh - End-to-end self-diagnostic verification matrix for Claude & Antigravity harnesses
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=================================================="
echo "   os-manager Multi-Agent Harness Self-Check      "
echo "=================================================="

# 1. Run unit test suite
echo "1. Running Hook & Guardrail Test Suite..."
"${WORKSPACE_ROOT}/tests/test_harness.sh"

# 2. Validate Multi-Agent Sync
echo "2. Validating Multi-Agent Skill & Harness Bridge..."
"${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh"

# 3. Validate Claude Settings JSON syntax
echo "3. Validating .claude/settings.json configuration..."
jq empty "${WORKSPACE_ROOT}/.claude/settings.json"
echo "   [PASS] Claude Settings configuration valid."

# 4. Validate Antigravity JSON configurations & verify harness
echo "4. Validating Antigravity .agents configurations & integrity..."
jq empty "${WORKSPACE_ROOT}/.agents/hooks.json"
"${WORKSPACE_ROOT}/scripts/import_claude_to_antigravity.sh" --verify-only
echo "   [PASS] Antigravity .agents harness valid."

echo "=================================================="
echo "✓ ALL HARNESS COMPONENT CHECKS PASSED"
echo "=================================================="
