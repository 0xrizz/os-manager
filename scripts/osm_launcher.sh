#!/usr/bin/env bash
# Entrypoint launcher dispatching to Python CLI or bash fallbacks
set -euo pipefail
WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if command -v python3 >/dev/null 2>&1 && [ -f "${WORKSPACE_ROOT}/os_manager/cli.py" ]; then
    export PYTHONPATH="${WORKSPACE_ROOT}:${PYTHONPATH:-}"
    exec python3 -m os_manager.cli "$@"
else
    case "${1:-check}" in
        diag) exec "${WORKSPACE_ROOT}/scripts/sys_diag.sh" "${@:2}" ;;
        clean) exec "${WORKSPACE_ROOT}/scripts/clean_system.sh" "${@:2}" ;;
        perf) exec "${WORKSPACE_ROOT}/scripts/perf_tune.sh" "${@:2}" ;;
        check|*) exec "${WORKSPACE_ROOT}/tests/test_harness.sh" "${@:2}" ;;
    esac
fi
