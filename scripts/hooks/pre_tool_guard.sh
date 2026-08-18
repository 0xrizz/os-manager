#!/usr/bin/env bash
# scripts/hooks/pre_tool_guard.sh - PreToolUse deterministic security policy engine
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Read JSON payload from stdin
INPUT_JSON="$(cat)"

if [ -z "${INPUT_JSON}" ]; then
    exit 0
fi

# Extract tool name using jq (fail closed on malformed JSON)
if ! TOOL_NAME="$(echo "${INPUT_JSON}" | jq -r '.tool_name // .name // empty' 2>/dev/null)"; then
    echo "[HARNESS SECURITY] Failed to parse tool execution JSON payload. Failing closed." >&2
    exit 2
fi

# Source Performance Tracing Helper
if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    trace_start "PreToolUse" "${TOOL_NAME:-null}"
fi

notify_security_violation() {
    local reason="$1"
    local notifier="${WORKSPACE_ROOT}/scripts/notify_host.sh"
    if [ -x "${notifier}" ]; then
        "${notifier}" --type security --title "Security Blocked" --message "${reason}" --async 2>/dev/null & disown || true
    fi
}

# 1. Guard File Operations (Edit, Write, Read)
if [[ "${TOOL_NAME}" =~ ^(Edit|Write|Read)$ ]]; then
    TARGET_PATH="$(echo "${INPUT_JSON}" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')"
    if [ -n "${TARGET_PATH}" ]; then
        CANONICAL_PATH="$(realpath -m "${TARGET_PATH}" 2>/dev/null || echo "${TARGET_PATH}")"

        # Invariant Block: Windows Host System Directories
        if [[ "${CANONICAL_PATH}" =~ ^/mnt/c/(Windows|Program\ Files|Program\ Files\ \(x86\)|Users/[^/]+/AppData) ]]; then
            if [[ "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
                echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Modification of Windows Host System files is strictly forbidden: ${TARGET_PATH}" >&2
                notify_security_violation "Modification of Windows Host System files blocked: ${TARGET_PATH}"
                exit 2
            fi
        fi

        # Invariant Block: Linux Core System Sabotage
        if [[ "${CANONICAL_PATH}" =~ ^/(etc/shadow|etc/passwd|boot/|dev/) ]]; then
            if [[ "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
                echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Modification of core Linux system files is strictly forbidden: ${TARGET_PATH}" >&2
                notify_security_violation "Modification of core Linux system files blocked: ${TARGET_PATH}"
                exit 2
            fi
        fi
    fi
    exit 0
fi

# 2. Guard Shell Executions (Bash)
if [ "${TOOL_NAME}" = "Bash" ]; then
    CMD="$(echo "${INPUT_JSON}" | jq -r '.tool_input.command // empty')"

    if [ -z "${CMD}" ]; then
        exit 0
    fi

    # Invariant Block: Destructive Root / Home Obliteration
    # shellcheck disable=SC2016
    if echo "${CMD}" | grep -qE '\brm\s+-[rRfF]*\s+(/|/\*|~|~/\*|\$HOME|\$HOME/\*|/home/[^/]+/?(\*|\.))([;&|[:space:]]|$)'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Destructive deletion of root or home directory is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Root or home deletion blocked: ${CMD}"
        exit 2
    fi

    # Invariant Block: WSL Lifecycle Sabotage
    if echo "${CMD}" | grep -qE '\b(wsl|wsl\.exe)\s+--(unregister|shutdown|terminate)\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): WSL instance lifecycle termination commands are strictly forbidden: ${CMD}" >&2
        notify_security_violation "WSL instance termination blocked: ${CMD}"
        exit 2
    fi

    # Invariant Block: Raw Disk Partitioning & Formatting
    if echo "${CMD}" | grep -qE '\b(mkfs(\.[a-z0-9]+)?|fdisk|parted|dd\s+if=.*of=/dev/sd[a-z])\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Raw disk formatting and block device alteration is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Raw disk formatting blocked: ${CMD}"
        exit 2
    fi

    # Invariant Block: Indiscriminate Package Purging (Generalized across all distros)
    if echo "${CMD}" | grep -qE '\b(apt|apt-get|pacman|dnf|zypper|apk)\s+(purge|remove|del|-Rcs)\s+(\*|all|--all)([;&|[:space:]]|\b|$)' || \
       echo "${CMD}" | grep -qE '\b(apt|apt-get|dpkg)\s+(--purge\s+)?(purge|remove)\s+-[a-zA-Z0-9]*\*([;&|[:space:]]|\b|$)' || \
       echo "${CMD}" | grep -qE '\bpacman\s+-[Rksu]+\s+.*(\b|\s)(base|systemd|glibc|linux-firmware)(\b|\s|$)' || \
       echo "${CMD}" | grep -qE '\bdnf\s+(remove|erase)\s+-[a-zA-Z0-9]*\*([;&|[:space:]]|\b|$)'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Destructive mass package removal is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Mass package purge blocked: ${CMD}"
        exit 2
    fi

    # Invariant Block: Dangerous Container Privilege Escalation
    if echo "${CMD}" | grep -qE '\bpodman\s+run\b.*\b(--privileged|--pid=host|--net=host|--cap-add=ALL|-v\s+/(dev|proc|sys|root|etc))\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Container privilege escalation is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Container privilege escalation blocked: ${CMD}"
        exit 2
    fi

    # Tier 2 Fast-Path: Pre-authorized maintenance & diagnostic scripts
    TIER2_SCRIPTS="sys_diag|clean_system|update_runtimes|wsl_snapshot|dotfiles_sync|tmux_agents|harness_check|perf_tune|manage_timers|compact_host_disk|notify_host|hook_benchmark|bus_send|post_bootstrap|sandbox_exec"
    if echo "${CMD}" | grep -qE "(^|[;&|[:space:]])(\\./scripts/|scripts/)?(${TIER2_SCRIPTS})\\.sh(\\s|$)"; then
        exit 0
    fi
    if echo "${CMD}" | grep -qE "(^|[;&|[:space:]])(\\./scripts/|scripts/)?agent_bus\\.py(\\s|$)"; then
        exit 0
    fi

    exit 0
fi

exit 0
