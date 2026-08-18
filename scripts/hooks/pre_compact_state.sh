#!/usr/bin/env bash
# scripts/hooks/pre_compact_state.sh - PreCompact state snapshotter
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS_DIR="${WORKSPACE_ROOT}/backups/logs"
mkdir -p "${LOGS_DIR}"

if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    trace_start "PreCompact" "null"
fi

SNAPSHOT_FILE="${LOGS_DIR}/compact_snapshot.json"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

GIT_STATUS="$(git status --porcelain 2>/dev/null || echo "not-a-git-repo")"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"

jq -n \
  --arg ts "${TIMESTAMP}" \
  --arg branch "${CURRENT_BRANCH}" \
  --arg git_status "${GIT_STATUS}" \
  '{timestamp: $ts, branch: $branch, git_status: $git_status}' > "${SNAPSHOT_FILE}"

exit 0
