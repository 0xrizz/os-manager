#!/usr/bin/env bash
# scripts/sync_agent_skills.sh - Multi-Agent Single Source of Truth (SSOT) & Standalone Harness Bridge
# NOTE: Skills remain scoped strictly within project workspaces (.claude/skills/ and .agents/skills/)
# and are NOT automatically promoted to global user home directories (~/.claude or ~/.gemini)
# unless explicitly requested with --global.
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_PROJECT_SKILLS="${WORKSPACE_ROOT}/.claude/skills"
AGENTS_PROJECT_SKILLS="${WORKSPACE_ROOT}/.agents/skills"
PROMOTE_GLOBAL=0

if [ "${1:-}" = "--global" ]; then
    PROMOTE_GLOBAL=1
fi

echo "=== Checking Multi-Agent Skills (Claude: .claude/skills | Antigravity: .agents/skills) ==="

CLAUDE_SKILLS_COUNT=0
for skill_path in "${CLAUDE_PROJECT_SKILLS}"/*; do
    if [ -d "${skill_path}" ]; then
        CLAUDE_SKILLS_COUNT=$((CLAUDE_SKILLS_COUNT + 1))
    fi
done

AGENTS_SKILLS_COUNT=0
if [ -d "${AGENTS_PROJECT_SKILLS}" ]; then
    for skill_path in "${AGENTS_PROJECT_SKILLS}"/*; do
        if [ -d "${skill_path}" ]; then
            AGENTS_SKILLS_COUNT=$((AGENTS_SKILLS_COUNT + 1))
        fi
    done
fi

echo "✓ Verified ${CLAUDE_SKILLS_COUNT} Claude skills in .claude/skills/"
echo "✓ Verified ${AGENTS_SKILLS_COUNT} Antigravity skills in .agents/skills/"

if [ "${PROMOTE_GLOBAL}" -eq 1 ]; then
    GLOBAL_CLAUDE_SKILLS="${HOME}/.claude/skills"
    GLOBAL_ANTIGRAVITY_SKILLS="${HOME}/.gemini/config/skills"
    mkdir -p "${GLOBAL_CLAUDE_SKILLS}" "${GLOBAL_ANTIGRAVITY_SKILLS}"

    for skill_path in "${CLAUDE_PROJECT_SKILLS}"/*; do
        if [ -d "${skill_path}" ]; then
            skill_name="$(basename "${skill_path}")"
            ln -sfn "${skill_path}" "${GLOBAL_CLAUDE_SKILLS}/${skill_name}"
        fi
    done

    for skill_path in "${AGENTS_PROJECT_SKILLS}"/*; do
        if [ -d "${skill_path}" ]; then
            skill_name="$(basename "${skill_path}")"
            ln -sfn "${skill_path}" "${GLOBAL_ANTIGRAVITY_SKILLS}/${skill_name}"
        fi
    done
    echo "✓ Promoted skills to global user home directories."
fi
