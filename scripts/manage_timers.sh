#!/usr/bin/env bash
# scripts/manage_timers.sh - Install and manage os-manager systemd user timers
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
ACTION="${1:-status}"

install_units() {
    echo "=== Installing OS-Manager Systemd User Units ==="
    mkdir -p "${SYSTEMD_USER_DIR}"
    cp "${WORKSPACE_ROOT}/systemd/os-maintenance.service" "${SYSTEMD_USER_DIR}/"
    cp "${WORKSPACE_ROOT}/systemd/os-maintenance.timer" "${SYSTEMD_USER_DIR}/"

    systemctl --user daemon-reload
    systemctl --user enable --now os-maintenance.timer
    echo "✓ Timer installed and activated."
}

uninstall_units() {
    echo "=== Disabling OS-Manager Systemd User Units ==="
    systemctl --user disable --now os-maintenance.timer || true
    rm -f "${SYSTEMD_USER_DIR}/os-maintenance.service"
    rm -f "${SYSTEMD_USER_DIR}/os-maintenance.timer"
    systemctl --user daemon-reload
    echo "✓ Timer disabled and uninstalled."
}

check_status() {
    echo "=== OS-Manager Systemd User Timer Status ==="
    systemctl --user list-timers --all | grep -E 'os-maintenance|NEXT' || echo "No active timers found."
}

case "${ACTION}" in
    install|enable)
        install_units
        ;;
    uninstall|disable)
        uninstall_units
        ;;
    status)
        check_status
        ;;
    *)
        echo "Usage: $0 {install|uninstall|status}"
        exit 1
        ;;
esac
