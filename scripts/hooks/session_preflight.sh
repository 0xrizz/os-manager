#!/usr/bin/env bash
# scripts/hooks/session_preflight.sh - SessionStart lifecycle hook
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS_DIR="${WORKSPACE_ROOT}/backups/logs"
mkdir -p "${LOGS_DIR}"

# Source Performance Tracing Helper
if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    trace_start "SessionStart" "null"
fi

# 1. RAM / Resource inspection
AVAILABLE_MEM_MB=$(free -m | awk '/^Mem:/{print $7}')
if [ -n "${AVAILABLE_MEM_MB}" ] && [ "${AVAILABLE_MEM_MB}" -lt 300 ]; then
    echo "[WARN] Low memory in WSL2: ${AVAILABLE_MEM_MB}MB available." >&2
fi

# 2. Check essential binaries
MISSING_TOOLS=()
for tool in jq python3 uv node; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
        MISSING_TOOLS+=("${tool}")
    fi
done

# shellcheck disable=SC2034
STATUS="OK"
if [ ${#MISSING_TOOLS[@]} -gt 0 ]; then
    # shellcheck disable=SC2034
    STATUS="DEGRADED (missing: ${MISSING_TOOLS[*]})"
fi

# 3. Synchronize agent skill symlinks if sync script exists
if [ -x "${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh" ]; then
    "${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh" >/dev/null 2>&1 || true
fi

exit 0
