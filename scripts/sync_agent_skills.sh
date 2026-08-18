#!/usr/bin/env bash
# scripts/sync_agent_skills.sh - Multi-Agent Single Source of Truth (SSOT) Symlink Bridge
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_SKILLS="${WORKSPACE_ROOT}/.claude/skills"
UNIVERSAL_SKILLS="${WORKSPACE_ROOT}/.agents/skills"
ANTIGRAVITY_SKILLS="${HOME}/.gemini/config/skills"

mkdir -p "${UNIVERSAL_SKILLS}"
mkdir -p "${ANTIGRAVITY_SKILLS}"

echo "=== Synchronizing Multi-Agent Skills (SSOT: .claude/skills) ==="

# 1. Clean broken symlinks in targets
find "${UNIVERSAL_SKILLS}" -xtype l -delete
find "${ANTIGRAVITY_SKILLS}" -xtype l -delete

# 2. Propagate to Universal Agent standard (.agents/skills/) using relative symlinks
for skill_path in "${CLAUDE_SKILLS}"/*; do
    if [ -d "${skill_path}" ]; then
        skill_name="$(basename "${skill_path}")"
        # Relative link: ../../.claude/skills/<name>
        ln -sfn "../../.claude/skills/${skill_name}" "${UNIVERSAL_SKILLS}/${skill_name}"
    fi
done

# 3. Propagate to Google Antigravity (~/.gemini/config/skills/) using absolute symlinks
for skill_path in "${CLAUDE_SKILLS}"/*; do
    if [ -d "${skill_path}" ]; then
        skill_name="$(basename "${skill_path}")"
        ln -sfn "${skill_path}" "${ANTIGRAVITY_SKILLS}/${skill_name}"
    fi
done

echo "✓ Synchronized $(find "${UNIVERSAL_SKILLS}" -mindepth 1 -maxdepth 1 | wc -l) skills to .agents/skills/ (Universal Agent)"
echo "✓ Synchronized $(find "${ANTIGRAVITY_SKILLS}" -mindepth 1 -maxdepth 1 | wc -l) skills to ~/.gemini/config/skills/ (Google Antigravity)"
