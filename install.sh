#!/usr/bin/env bash
# install.sh - Standalone POSIX shell installer for os-manager
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="${SCRIPT_DIR}"

MODE="local"
DRY_RUN=false
PROJECT_DIR=""

show_help() {
    cat <<HELP
Usage: $(basename "$0") [OPTIONS]

Install, scaffold, or uninstall the os-manager control plane.

Options:
  --global               Configure global Claude Code hooks in ~/.claude/settings.json
  --project <dir>        Scaffold Claude Code governance files into a project directory
  --uninstall            Remove os-manager symlinks, configurations, and daemons
  --dry-run              Display installation operations without modifying files
  -h, --help             Show this help message and exit
HELP
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --global)
            MODE="global"
            shift
            ;;
        --project)
            MODE="project"
            PROJECT_DIR="$2"
            shift 2
            ;;
        --uninstall)
            MODE="uninstall"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown argument '$1'" >&2
            show_help >&2
            exit 1
            ;;
    esac
done

execute_op() {
    local desc="$1"
    shift
    if [ "${DRY_RUN}" = true ]; then
        echo "[DRY RUN] ${desc}: $*"
    else
        "$@"
    fi
}

install_local() {
    local bin_dir="${HOME}/.local/bin"
    local state_dir="${HOME}/.local/state/os-manager/logs"
    local share_dir="${HOME}/.local/share/os-manager/backups"
    local target_bin="${bin_dir}/osm"

    echo "=== Installing os-manager locally ==="
    execute_op "Create binary directory" mkdir -p "${bin_dir}"
    execute_op "Create state log directory" mkdir -p "${state_dir}"
    execute_op "Create backup share directory" mkdir -p "${share_dir}"

    local launcher="${SOURCE_ROOT}/scripts/osm_launcher.sh"
    if [ ! -f "${launcher}" ]; then
        if [ "${DRY_RUN}" = true ]; then
            echo "[DRY RUN] Create launcher: ${launcher}"
        else
            cat <<'EOF' > "${SOURCE_ROOT}/scripts/osm_launcher.sh"
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
EOF
            chmod +x "${SOURCE_ROOT}/scripts/osm_launcher.sh"
        fi
    fi

    execute_op "Link osm executable" ln -sf "${SOURCE_ROOT}/scripts/osm_launcher.sh" "${target_bin}"
    echo "Installation complete. Executable available at ${target_bin}"
}

scaffold_project() {
    local target="${PROJECT_DIR}"
    if [ -z "${target}" ]; then
        echo "Error: Target project directory must be specified with --project <dir>" >&2
        exit 1
    fi

    echo "=== Scaffolding Claude Code governance in ${target} ==="
    execute_op "Create .claude directory" mkdir -p "${target}/.claude/rules" "${target}/.claude/commands" "${target}/.claude/skills"

    if [ -f "${SOURCE_ROOT}/.claude/settings.json" ]; then
        execute_op "Copy settings.json" cp -n "${SOURCE_ROOT}/.claude/settings.json" "${target}/.claude/settings.json" || true
    fi

    if [ -d "${SOURCE_ROOT}/.claude/rules" ]; then
        execute_op "Copy rules" cp -rn "${SOURCE_ROOT}/.claude/rules/"* "${target}/.claude/rules/" || true
    fi

    echo "Project scaffolding completed in ${target}"
}

uninstall_local() {
    local target_bin="${HOME}/.local/bin/osm"
    echo "=== Uninstalling os-manager ==="
    if [ -e "${target_bin}" ] || [ -L "${target_bin}" ]; then
        execute_op "Remove binary symlink" rm -f "${target_bin}"
        echo "Removed ${target_bin}"
    else
        echo "No binary symlink found at ${target_bin}"
    fi
    echo "Uninstall completed cleanly."
}

case "${MODE}" in
    local|global)
        install_local
        ;;
    project)
        scaffold_project
        ;;
    uninstall)
        uninstall_local
        ;;
esac
