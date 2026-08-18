#!/usr/bin/env bash
# scripts/hooks/session_cleanup.sh - SessionEnd lifecycle hook
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS_DIR="${WORKSPACE_ROOT}/backups/logs"
mkdir -p "${LOGS_DIR}"

AUDIT_LOG="${LOGS_DIR}/harness_audit.jsonl"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Clean ephemeral test / temp artifacts if present
rm -f /tmp/os_manager_temp_* 2>/dev/null || true

echo "{\"timestamp\":\"${TIMESTAMP}\",\"event\":\"SessionEnd\",\"status\":\"SUCCESS\"}" >> "${AUDIT_LOG}"
exit 0
