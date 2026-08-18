#!/usr/bin/env bash
# scripts/manage_timers.sh - Install and manage os-manager systemd user timers and services
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"
ACTION="${1:-status}"

# Normalize flag syntax (--status -> status)
ACTION="${ACTION#--}"

install_units() {
    echo "=== Installing OS-Manager Systemd User Units ==="
    mkdir -p "${SYSTEMD_USER_DIR}"
    cp "${WORKSPACE_ROOT}/systemd/os-maintenance.service" "${SYSTEMD_USER_DIR}/"
    cp "${WORKSPACE_ROOT}/systemd/os-maintenance.timer" "${SYSTEMD_USER_DIR}/"
    cp "${WORKSPACE_ROOT}/systemd/os-metrics-exporter.service" "${SYSTEMD_USER_DIR}/"

    systemctl --user daemon-reload
    systemctl --user enable --now os-maintenance.timer
    systemctl --user enable --now os-metrics-exporter.service
    echo "✓ Maintenance timer and metrics exporter installed and activated."
}

uninstall_units() {
    echo "=== Disabling OS-Manager Systemd User Units ==="
    systemctl --user disable --now os-maintenance.timer 2>/dev/null || true
    systemctl --user disable --now os-metrics-exporter.service 2>/dev/null || true
    rm -f "${SYSTEMD_USER_DIR}/os-maintenance.service"
    rm -f "${SYSTEMD_USER_DIR}/os-maintenance.timer"
    rm -f "${SYSTEMD_USER_DIR}/os-metrics-exporter.service"
    systemctl --user daemon-reload
    echo "✓ Maintenance timer and metrics exporter disabled and uninstalled."
}

check_status() {
    echo "=== OS-Manager Systemd User Timer Status ==="
    systemctl --user list-timers --all | grep -E 'os-maintenance|NEXT' || echo "No active maintenance timers found."
    echo ""
    echo "=== OS-Manager Systemd Exporter Status ==="
    systemctl --user status os-metrics-exporter.service --no-pager 2>/dev/null || echo "Exporter service inactive or uninstalled."
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
        echo "Usage: $0 {install|uninstall|status|enable|disable|--status|--enable|--disable}"
        exit 1
        ;;
esac
