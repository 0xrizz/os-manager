#!/usr/bin/env bash
# scripts/tune_system.sh - Kernel Sysctl, NVMe TRIM, PipeWire, and UFW Security Tuning
set -euo pipefail

SYSCTL_CONF_PATH="/etc/sysctl.d/99-osm-performance.conf"

log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_pass()  { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; }

apply_sysctl_tuning() {
    log_info "Applying Linux kernel performance sysctl parameters..."
    if [[ $EUID -ne 0 ]]; then
        cat <<EOF | sudo tee "${SYSCTL_CONF_PATH}" >/dev/null
# os-manager Debian 13 Kernel Performance Tuning
vm.swappiness = 10
vm.vfs_cache_pressure = 50
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 1024
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
EOF
        sudo sysctl --system >/dev/null 2>&1 || sudo sysctl -p "${SYSCTL_CONF_PATH}" 2>/dev/null || true
    else
        cat <<EOF | tee "${SYSCTL_CONF_PATH}" >/dev/null
# os-manager Debian 13 Kernel Performance Tuning
vm.swappiness = 10
vm.vfs_cache_pressure = 50
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 1024
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
EOF
        sysctl --system >/dev/null 2>&1 || sysctl -p "${SYSCTL_CONF_PATH}" 2>/dev/null || true
    fi
    log_pass "Kernel sysctl configuration active at: ${SYSCTL_CONF_PATH}"
}

audit_sysctl() {
    log_info "Auditing kernel sysctl parameters..."
    local swappiness
    swappiness="$(sysctl -n vm.swappiness 2>/dev/null || echo "unknown")"
    local bbr
    bbr="$(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null || echo "unknown")"
    local inotify
    inotify="$(sysctl -n fs.inotify.max_user_watches 2>/dev/null || echo "unknown")"

    log_info "vm.swappiness: ${swappiness} (target: 10)"
    log_info "TCP Congestion Control: ${bbr} (target: bbr)"
    log_info "fs.inotify.max_user_watches: ${inotify} (target: 524288)"
}

enable_nvme_trim() {
    log_info "Enabling periodic NVMe storage fstrim.timer..."
    if command -v systemctl >/dev/null 2>&1; then
        if [[ $EUID -ne 0 ]]; then
            sudo systemctl enable --now fstrim.timer 2>/dev/null || true
        else
            systemctl enable --now fstrim.timer 2>/dev/null || true
        fi
        log_pass "fstrim.timer enabled and active."
    else
        log_warn "systemctl not available; cannot enable fstrim.timer."
    fi
}

status_nvme_trim() {
    if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet fstrim.timer 2>/dev/null; then
        log_pass "fstrim.timer: Active"
    else
        log_warn "fstrim.timer: Inactive"
    fi
}

status_audio() {
    log_info "Auditing PipeWire audio stack..."
    if command -v pipewire >/dev/null 2>&1; then
        log_pass "PipeWire binary found: $(command -v pipewire)"
    else
        log_warn "PipeWire binary not found."
    fi

    if command -v wireplumber >/dev/null 2>&1; then
        log_pass "WirePlumber session manager found: $(command -v wireplumber)"
    else
        log_warn "WirePlumber session manager not found."
    fi
}

enable_firewall() {
    log_info "Configuring and enabling UFW firewall..."
    if ! command -v ufw >/dev/null 2>&1; then
        log_error "UFW is not installed. Install with: sudo apt install -y ufw"
        return 1
    fi
    if [[ $EUID -ne 0 ]]; then
        sudo ufw default deny incoming
        sudo ufw default allow outgoing
        sudo ufw --force enable
    else
        ufw default deny incoming
        ufw default allow outgoing
        ufw --force enable
    fi
    log_pass "UFW firewall enabled with default deny incoming / allow outgoing."
}

status_firewall() {
    if command -v ufw >/dev/null 2>&1; then
        local ufw_st
        ufw_st="$(ufw status 2>/dev/null | head -n 1 || echo "unknown")"
        log_info "UFW Firewall: ${ufw_st}"
    else
        log_warn "UFW Firewall not installed."
    fi
}

audit_system() {
    echo "=================================================="
    echo "      Kernel, Storage & Security Hardening Audit  "
    echo "=================================================="
    audit_sysctl
    status_nvme_trim
    status_audio
    status_firewall
    echo "=================================================="
}

show_help() {
    cat <<EOF
Usage: $(basename "$0") [OPTION] [SUBCOMMAND]

Options:
    --sysctl [apply|audit]     Apply or audit kernel sysctl performance configuration
    --trim [enable|status]     Enable periodic TRIM or check fstrim.timer status
    --audio [status]           Check PipeWire / WirePlumber audio stack status
    --firewall [enable|status] Enable UFW firewall or check status
    --audit                    Run comprehensive audit across all subsystems
    --help, -h                 Show this help message
EOF
}

main() {
    local action="${1:---audit}"
    local subaction="${2:-}"

    case "${action}" in
        --sysctl)
            if [[ "${subaction}" == "audit" ]]; then
                audit_sysctl
            else
                apply_sysctl_tuning
            fi
            ;;
        --trim)
            if [[ "${subaction}" == "status" ]]; then
                status_nvme_trim
            else
                enable_nvme_trim
            fi
            ;;
        --audio)
            status_audio
            ;;
        --firewall)
            if [[ "${subaction}" == "enable" ]]; then
                enable_firewall
            else
                status_firewall
            fi
            ;;
        --audit)
            audit_system
            ;;
        --help|-h)
            show_help
            ;;
        *)
            show_help
            exit 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
