#!/usr/bin/env bash
# scripts/harness_check.sh - End-to-end self-diagnostic verification matrix
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=================================================="
echo "      os-manager Claude Harness Self-Check        "
echo "=================================================="

# 1. Run unit test suite
echo "1. Running Hook & Guardrail Test Suite..."
"${WORKSPACE_ROOT}/tests/test_harness.sh"

# 2. Validate Multi-Agent Sync
echo "2. Validating Multi-Agent Skill Symlinks..."
"${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh"

# 3. Validate Settings JSON syntax
echo "3. Validating .claude/settings.json configuration..."
jq empty "${WORKSPACE_ROOT}/.claude/settings.json"
echo "   [PASS] Settings configuration valid."

echo "=================================================="
echo "✓ ALL HARNESS COMPONENT CHECKS PASSED"
echo "=================================================="
