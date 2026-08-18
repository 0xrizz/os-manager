#!/usr/bin/env bash
# scripts/hooks/pre_tool_guard.sh - PreToolUse deterministic security policy engine
set -euo pipefail

# shellcheck disable=SC2034
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

# 1. Guard File Operations (Edit, Write, Read)
if [[ "${TOOL_NAME}" =~ ^(Edit|Write|Read)$ ]]; then
    TARGET_PATH="$(echo "${INPUT_JSON}" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')"
    if [ -n "${TARGET_PATH}" ]; then
        CANONICAL_PATH="$(realpath -m "${TARGET_PATH}" 2>/dev/null || echo "${TARGET_PATH}")"

        # Invariant Block: Windows Host System Directories
        if [[ "${CANONICAL_PATH}" =~ ^/mnt/c/(Windows|Program\ Files|Program\ Files\ \(x86\)|Users/[^/]+/AppData) ]]; then
            if [[ "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
                echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Modification of Windows Host System files is strictly forbidden: ${TARGET_PATH}" >&2
                exit 2
            fi
        fi

        # Invariant Block: Linux Core System Sabotage
        if [[ "${CANONICAL_PATH}" =~ ^/(etc/shadow|etc/passwd|boot/|dev/) ]]; then
            if [[ "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
                echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Modification of core Linux system files is strictly forbidden: ${TARGET_PATH}" >&2
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
        exit 2
    fi

    # Invariant Block: WSL Lifecycle Sabotage
    if echo "${CMD}" | grep -qE '\b(wsl|wsl\.exe)\s+--(unregister|shutdown|terminate)\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): WSL instance lifecycle termination commands are strictly forbidden: ${CMD}" >&2
        exit 2
    fi

    # Invariant Block: Raw Disk Partitioning & Formatting
    if echo "${CMD}" | grep -qE '\b(mkfs(\.[a-z0-9]+)?|fdisk|parted|dd\s+if=.*of=/dev/sd[a-z])\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Raw disk formatting and block device alteration is strictly forbidden: ${CMD}" >&2
        exit 2
    fi

    # Invariant Block: Indiscriminate Package Purging
    if echo "${CMD}" | grep -qE '\b(apt|apt-get|dpkg)\s+(--purge\s+)?(purge|remove)\s+(-y\s+)?\*(\b|[;&|[:space:]]|$)'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Wildcard package purge is strictly forbidden: ${CMD}" >&2
        exit 2
    fi

    # Tier 2 Fast-Path: Pre-authorized maintenance & diagnostic scripts
    if echo "${CMD}" | grep -qE '(^|[;&|[:space:]])(\./scripts/|scripts/)?(sys_diag|clean_system|update_runtimes|wsl_snapshot|dotfiles_sync|tmux_agents|harness_check|perf_tune|manage_timers)\.sh(\s|$)'; then
        exit 0
    fi

    exit 0
fi

exit 0
