#!/usr/bin/env bash
# scripts/sandbox_bwrap.sh - Ephemeral rootless Bubblewrap sandbox wrapper for os-manager
# ponytail: basic bwrap args wrapper; add seccomp filter and cgroup limit flags when resource caps needed
set -euo pipefail

if ! command -v bwrap >/dev/null 2>&1; then
    echo "[SANDBOX ERROR] bubblewrap (bwrap) is not installed." >&2
    exit 1
fi

WORKDIR="$(pwd)"
ALLOW_NET=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workdir)
            WORKDIR="$2"
            shift 2
            ;;
        --allow-net)
            ALLOW_NET=true
            shift
            ;;
        --)
            shift
            break
            ;;
        *)
            break
            ;;
    esac
done

if [[ $# -eq 0 ]]; then
    echo "Usage: $0 [--workdir <path>] [--allow-net] -- <command...>" >&2
    exit 1
fi

CMD=("$@")

BWRAP_ARGS=(
    --ro-bind / /
    --dev /dev
    --proc /proc
    --tmpfs /tmp
    --tmpfs /run
    --bind "${WORKDIR}" "${WORKDIR}"
)

if [[ -d "${HOME}/.cache" ]]; then
    BWRAP_ARGS+=(--bind "${HOME}/.cache" "${HOME}/.cache")
fi

BWRAP_ARGS+=(
    --chdir "${WORKDIR}"
    --unshare-all
    --die-with-parent
)

if [ "${ALLOW_NET}" = true ]; then
    BWRAP_ARGS+=(--share-net)
fi

exec bwrap "${BWRAP_ARGS[@]}" "${CMD[@]}"
