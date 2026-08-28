#!/usr/bin/env bash
# scripts/sudo_exec.sh - Hardened non-interactive sudo execution wrapper
# Adheres to os-manager zero-trust credential streaming & zero-leakage invariants.

set -eo pipefail

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 <command> [args...]" >&2
    echo "Executes privileged commands non-interactively without blocking on TTY prompts." >&2
    exit 1
fi

# 1. Probe for passwordless sudo first
if sudo -n true 2>/dev/null; then
    exec sudo "$@"
fi

# 2. Resolve project directory and .env location
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-}"
if [ -z "${PROJECT_ROOT}" ] || [ ! -d "${PROJECT_ROOT}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
fi

USER_HOME="${HOME:-/root}"
ENV_FILE=""
CANDIDATE_PATHS=(
    "${PROJECT_ROOT}/.env"
    "${USER_HOME}/dev/os-manager/.env"
    "/mnt/data/dev/os-manager/.env"
    "/mnt/d/dev/os-manager/.env"
)

for cand in "${CANDIDATE_PATHS[@]}"; do
    if [ -f "${cand}" ]; then
        ENV_FILE="${cand}"
        break
    fi
done

# 3. Extract SUDO_PASSWORD securely
SUDO_PASS="${SUDO_PASSWORD:-}"

if [ -z "${SUDO_PASS}" ] && [ -n "${ENV_FILE}" ]; then
    if grep -qE '^SUDO_PASSWORD=' "${ENV_FILE}" 2>/dev/null; then
        SUDO_PASS="$(grep -E '^SUDO_PASSWORD=' "${ENV_FILE}" | head -n 1 | cut -d '=' -f2- | tr -d '\r\n')"
    elif [ "$(wc -l < "${ENV_FILE}" 2>/dev/null || echo 0)" -le 2 ]; then
        # Fallback: single-line raw password in .env
        SUDO_PASS="$(head -n 1 "${ENV_FILE}" | tr -d '\r\n')"
    fi
fi

if [ -z "${SUDO_PASS}" ]; then
    echo "[SUDO_EXEC ERROR] Sudo privileges required but no password found in environment or .env file." >&2
    echo "Ensure SUDO_PASSWORD is set in ${PROJECT_ROOT}/.env" >&2
    exit 1
fi

# 4. Stream password securely via sudo -S with prompt suppressed
printf '%s\n' "${SUDO_PASS}" | sudo -S -p '' "$@"
RC=$?

# Clear password variable immediately
unset SUDO_PASS

exit "${RC}"
