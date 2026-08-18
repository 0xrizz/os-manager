#!/usr/bin/env bash
# scripts/hooks/session_cleanup.sh - SessionEnd lifecycle hook
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS_DIR="${WORKSPACE_ROOT}/backups/logs"
mkdir -p "${LOGS_DIR}"

if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    trace_start "SessionEnd" "null"
fi

# Clean ephemeral test / temp artifacts if present
rm -f /tmp/os_manager_temp_* 2>/dev/null || true

exit 0
