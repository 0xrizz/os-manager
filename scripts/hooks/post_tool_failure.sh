#!/usr/bin/env bash
# scripts/hooks/post_tool_failure.sh - PostToolUseFailure telemetry logger
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS_DIR="${WORKSPACE_ROOT}/backups/logs"
mkdir -p "${LOGS_DIR}"

ERROR_LOG="${LOGS_DIR}/harness_errors.jsonl"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
INPUT_JSON="$(cat)"

echo "{\"timestamp\":\"${TIMESTAMP}\",\"payload\":${INPUT_JSON:-{}}}" >> "${ERROR_LOG}"
exit 0
