#!/usr/bin/env bash
# tests/test_harness_isolation.sh - Validate zero-host pollution and workspace isolation
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GLOBAL_CLAUDE="${HOME}/.claude/skills"
GLOBAL_GEMINI="${HOME}/.gemini/config/skills"

echo "==> [ISO-01] Testing sync_agent_skills.sh default workspace isolation..."
# Count symlinks in global dirs before execution
BEFORE_CLAUDE_LINKS=$(find "${GLOBAL_CLAUDE}" -maxdepth 1 -type l 2>/dev/null | wc -l || echo 0)
BEFORE_GEMINI_LINKS=$(find "${GLOBAL_GEMINI}" -maxdepth 1 -type l 2>/dev/null | wc -l || echo 0)

"${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh" >/dev/null

AFTER_CLAUDE_LINKS=$(find "${GLOBAL_CLAUDE}" -maxdepth 1 -type l 2>/dev/null | wc -l || echo 0)
AFTER_GEMINI_LINKS=$(find "${GLOBAL_GEMINI}" -maxdepth 1 -type l 2>/dev/null | wc -l || echo 0)

if [ "${BEFORE_CLAUDE_LINKS}" -ne "${AFTER_CLAUDE_LINKS}" ] || [ "${BEFORE_GEMINI_LINKS}" -ne "${AFTER_GEMINI_LINKS}" ]; then
    echo "FAIL: sync_agent_skills.sh modified global directories without --global flag"
    exit 1
fi
echo "PASS: sync_agent_skills.sh does not pollute global directories."

echo "==> [ISO-02] Testing session_preflight.sh execution isolation..."
"${WORKSPACE_ROOT}/scripts/hooks/session_preflight.sh" >/dev/null

FINAL_CLAUDE_LINKS=$(find "${GLOBAL_CLAUDE}" -maxdepth 1 -type l 2>/dev/null | wc -l || echo 0)
FINAL_GEMINI_LINKS=$(find "${GLOBAL_GEMINI}" -maxdepth 1 -type l 2>/dev/null | wc -l || echo 0)

if [ "${FINAL_CLAUDE_LINKS}" -ne "${BEFORE_CLAUDE_LINKS}" ] || [ "${FINAL_GEMINI_LINKS}" -ne "${BEFORE_GEMINI_LINKS}" ]; then
    echo "FAIL: session_preflight.sh caused global directory pollution"
    exit 1
fi
echo "PASS: session_preflight.sh maintains workspace isolation."

echo "==> [ISO-03] Asserting absence of deprecated ~/.agent and ~/.agents directories..."
if [ -d "${HOME}/.agent" ] || [ -d "${HOME}/.agents" ]; then
    echo "FAIL: Deprecated ~/.agent or ~/.agents directory found in home"
    exit 1
fi
echo "PASS: No deprecated agent directories present."

echo "==> [ISO-04] Asserting absence of workspace .agents directory..."
if [ -d "${WORKSPACE_ROOT}/.agents" ]; then
    echo "FAIL: Deprecated .agents directory found in workspace"
    exit 1
fi
echo "PASS: Workspace .agents mirror absent."

echo "✓ All Harness Isolation checks passed."
exit 0
