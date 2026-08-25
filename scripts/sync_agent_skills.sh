#!/usr/bin/env bash
# scripts/sync_agent_skills.sh - Multi-Agent Single Source of Truth (SSOT) Symlink Bridge
# NOTE: Skills remain scoped strictly within project workspaces (.claude/skills/)
# and are NOT automatically promoted to global user home directories (~/.claude or ~/.gemini)
# unless explicitly requested with --global.
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_PROJECT_SKILLS="${WORKSPACE_ROOT}/.claude/skills"
PROMOTE_GLOBAL=0

if [ "${1:-}" = "--global" ]; then
    PROMOTE_GLOBAL=1
fi

echo "=== Checking Multi-Agent Skills (SSOT: .claude/skills) ==="

TOTAL_SKILLS=0
for skill_path in "${CLAUDE_PROJECT_SKILLS}"/*; do
    if [ -d "${skill_path}" ]; then
        TOTAL_SKILLS=$((TOTAL_SKILLS + 1))
    fi
done

echo "✓ Verified ${TOTAL_SKILLS} project skills scoped to .claude/skills/"

if [ "${PROMOTE_GLOBAL}" -eq 1 ]; then
    GLOBAL_CLAUDE_SKILLS="${HOME}/.claude/skills"
    GLOBAL_ANTIGRAVITY_SKILLS="${HOME}/.gemini/config/skills"
    mkdir -p "${GLOBAL_CLAUDE_SKILLS}" "${GLOBAL_ANTIGRAVITY_SKILLS}"

    for skill_path in "${CLAUDE_PROJECT_SKILLS}"/*; do
        if [ -d "${skill_path}" ]; then
            skill_name="$(basename "${skill_path}")"
            ln -sfn "${skill_path}" "${GLOBAL_CLAUDE_SKILLS}/${skill_name}"
            ln -sfn "${skill_path}" "${GLOBAL_ANTIGRAVITY_SKILLS}/${skill_name}"
        fi
    done
    echo "✓ Promoted ${TOTAL_SKILLS} skills to global user home directories."
fi
