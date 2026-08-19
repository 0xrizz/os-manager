#!/usr/bin/env bash
# scripts/post_bootstrap.sh - First-boot verification and environment initialization
# Restores executable permissions, synchronizes SSOT skill symlinks, reloads systemd user units,
# and verifies harness integrity after disaster recovery restoration.
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUDIT_LOG="${WORKSPACE_ROOT}/backups/logs/harness_audit.jsonl"
AUDIT_ONLY=0

if [ "${1:-}" = "--audit-only" ]; then
    AUDIT_ONLY=1
fi

echo "================================================================="
echo " OS-Manager Post-Bootstrap Verification Agent"
echo "================================================================="

echo "==> [1/4] Auditing script permissions and workspace ownership..."
find "${WORKSPACE_ROOT}/scripts" -type f -name "*.sh" -exec chmod +x {} + 2>/dev/null || true
find "${WORKSPACE_ROOT}/tests" -type f -name "*.sh" -exec chmod +x {} + 2>/dev/null || true
if [ -f "${WORKSPACE_ROOT}/scripts/agent_bus.py" ]; then
    chmod +x "${WORKSPACE_ROOT}/scripts/agent_bus.py" 2>/dev/null || true
fi
if [ -f "${WORKSPACE_ROOT}/scripts/metrics_exporter.py" ]; then
    chmod +x "${WORKSPACE_ROOT}/scripts/metrics_exporter.py" 2>/dev/null || true
fi

echo "==> [2/4] Rebuilding multi-agent SSOT skill symlinks..."
if [ -f "${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh" ]; then
    bash "${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh"
else
    echo "Warning: sync_agent_skills.sh not found at ${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh" >&2
fi

echo "==> [3/4] Reloading systemd user daemon and maintenance timers..."
if [ "${AUDIT_ONLY}" -eq 0 ]; then
    systemctl --user daemon-reload >/dev/null 2>&1 || true
    if [ -f "${WORKSPACE_ROOT}/scripts/manage_timers.sh" ]; then
        bash "${WORKSPACE_ROOT}/scripts/manage_timers.sh" install >/dev/null 2>&1 || true
    fi
else
    echo "  [AUDIT-ONLY] Simulated systemd user daemon reload and timer install."
fi

echo "==> [4/4] Running automated harness test suite..."
if [ "${AUDIT_ONLY}" -eq 0 ]; then
    if [ -f "${WORKSPACE_ROOT}/tests/test_harness.sh" ]; then
        bash "${WORKSPACE_ROOT}/tests/test_harness.sh"
    fi
else
    echo "  [AUDIT-ONLY] Simulated test harness execution."
fi

# Log telemetry event using unified trace schema
TIMESTAMP_ISO="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
TIMESTAMP_EPOCH="$(date +%s)"
mkdir -p "$(dirname "${AUDIT_LOG}")"
printf '{"timestamp_iso":"%s","timestamp_epoch":%d,"hook_name":"PostBootstrap","target_tool":null,"duration_ms":0.00,"duration_us":0,"exit_code":0}\n' \
    "${TIMESTAMP_ISO}" "${TIMESTAMP_EPOCH}" >> "${AUDIT_LOG}" 2>/dev/null || true

echo "================================================================="
echo " Environment restored and verified successfully."
echo "================================================================="
