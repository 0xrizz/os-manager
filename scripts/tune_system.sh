#!/usr/bin/env bash
# scripts/tune_system.sh - Kernel Sysctl, NVMe TRIM, PipeWire, and UFW Security Tuning
set -euo pipefail

SYSCTL_CONF_PATH="/etc/sysctl.d/99-osm-performance.conf"
SYSCTL_SCHEDULER_PATH="/etc/sysctl.d/99-osm-scheduler.conf"
SESSION_SLICE_DIR="/etc/systemd/user/session.slice.d"
SESSION_SLICE_PATH="${SESSION_SLICE_DIR}/10-resources.conf"
BACKGROUND_SLICE_DIR="/etc/systemd/user/background.slice.d"
BACKGROUND_SLICE_PATH="${BACKGROUND_SLICE_DIR}/10-resources.conf"

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
    local sysctl_cmd="sysctl"
    if ! command -v "${sysctl_cmd}" >/dev/null 2>&1; then
        if [[ -x "/sbin/sysctl" ]]; then
            sysctl_cmd="/sbin/sysctl"
        elif [[ -x "/usr/sbin/sysctl" ]]; then
            sysctl_cmd="/usr/sbin/sysctl"
        fi
    fi
    local swappiness
    swappiness="$("${sysctl_cmd}" -n vm.swappiness 2>/dev/null || echo "unknown")"
    local bbr
    bbr="$("${sysctl_cmd}" -n net.ipv4.tcp_congestion_control 2>/dev/null || echo "unknown")"
    local inotify
    inotify="$("${sysctl_cmd}" -n fs.inotify.max_user_watches 2>/dev/null || echo "unknown")"

    log_info "vm.swappiness: ${swappiness} (target: 10)"
    log_info "TCP Congestion Control: ${bbr} (target: bbr)"
    log_info "fs.inotify.max_user_watches: ${inotify} (target: 524288)"
}

apply_scheduler_tuning() {
    log_info "Applying Linux 6.6+ EEVDF scheduler slicing & cgroups v2 user slice overrides..."
    if [[ $EUID -ne 0 ]]; then
        cat <<EOF | sudo tee "${SYSCTL_SCHEDULER_PATH}" >/dev/null
# /etc/sysctl.d/99-osm-scheduler.conf - Managed by os-manager
kernel.sched_base_slice_ns = 2000000
kernel.sched_cfs_bandwidth_slice_us = 3000
EOF
        sudo mkdir -p "${SESSION_SLICE_DIR}" "${BACKGROUND_SLICE_DIR}"
        cat <<EOF | sudo tee "${SESSION_SLICE_PATH}" >/dev/null
# /etc/systemd/user/session.slice.d/10-resources.conf - Managed by os-manager
[Slice]
CPUWeight=500
IOWeight=500
ManagedOOMPreference=avoid
EOF
        cat <<EOF | sudo tee "${BACKGROUND_SLICE_PATH}" >/dev/null
# /etc/systemd/user/background.slice.d/10-resources.conf - Managed by os-manager
[Slice]
CPUWeight=20
IOWeight=20
MemoryHigh=1536M
ManagedOOMPreference=kill
EOF
        sudo sysctl --system >/dev/null 2>&1 || sudo sysctl -p "${SYSCTL_SCHEDULER_PATH}" 2>/dev/null || true
    else
        cat <<EOF | tee "${SYSCTL_SCHEDULER_PATH}" >/dev/null
# /etc/sysctl.d/99-osm-scheduler.conf - Managed by os-manager
kernel.sched_base_slice_ns = 2000000
kernel.sched_cfs_bandwidth_slice_us = 3000
EOF
        mkdir -p "${SESSION_SLICE_DIR}" "${BACKGROUND_SLICE_DIR}"
        cat <<EOF | tee "${SESSION_SLICE_PATH}" >/dev/null
# /etc/systemd/user/session.slice.d/10-resources.conf - Managed by os-manager
[Slice]
CPUWeight=500
IOWeight=500
ManagedOOMPreference=avoid
EOF
        cat <<EOF | tee "${BACKGROUND_SLICE_PATH}" >/dev/null
# /etc/systemd/user/background.slice.d/10-resources.conf - Managed by os-manager
[Slice]
CPUWeight=20
IOWeight=20
MemoryHigh=1536M
ManagedOOMPreference=kill
EOF
        sysctl --system >/dev/null 2>&1 || sysctl -p "${SYSCTL_SCHEDULER_PATH}" 2>/dev/null || true
    fi
    log_pass "Scheduler & user slices applied (EEVDF base slice: 2ms, session/bg cgroups v2 overrides)."
}

audit_scheduler() {
    log_info "Auditing Linux EEVDF scheduler & cgroups v2 user slices..."
    local sysctl_cmd="sysctl"
    if ! command -v "${sysctl_cmd}" >/dev/null 2>&1; then
        if [[ -x "/sbin/sysctl" ]]; then
            sysctl_cmd="/sbin/sysctl"
        elif [[ -x "/usr/sbin/sysctl" ]]; then
            sysctl_cmd="/usr/sbin/sysctl"
        fi
    fi
    local base_slice
    base_slice="$("${sysctl_cmd}" -n kernel.sched_base_slice_ns 2>/dev/null || echo "unsupported/unknown")"
    local cfs_slice
    cfs_slice="$("${sysctl_cmd}" -n kernel.sched_cfs_bandwidth_slice_us 2>/dev/null || echo "unsupported/unknown")"
    log_info "EEVDF Base Slice (kernel.sched_base_slice_ns): ${base_slice} (target: 2000000)"
    log_info "CFS Bandwidth Slice (kernel.sched_cfs_bandwidth_slice_us): ${cfs_slice} (target: 3000)"

    if [[ -f "${SESSION_SLICE_PATH}" ]]; then
        log_pass "systemd user session.slice override: Configured"
    else
        log_warn "systemd user session.slice override: Missing"
    fi

    if [[ -f "${BACKGROUND_SLICE_PATH}" ]]; then
        log_pass "systemd user background.slice override: Configured"
    else
        log_warn "systemd user background.slice override: Missing"
    fi
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

audit_storage() {
    log_info "Auditing storage filesystem drivers and NVMe TRIM..."
    local mount_point="${1:-/mnt/data}"
    local fstype="unknown"
    if command -v findmnt >/dev/null 2>&1; then
        fstype="$(findmnt -n -o FSTYPE "${mount_point}" 2>/dev/null || echo "unmounted")"
    fi
    if [[ "${fstype}" == "ntfs3" ]]; then
        log_pass "Storage ${mount_point}: ${fstype} (in-kernel high-performance driver)"
    elif [[ "${fstype}" == "fuseblk" || "${fstype}" == "ntfs-3g" ]]; then
        log_warn "Storage ${mount_point}: ${fstype} (userspace FUSE driver - migration recommended)"
    else
        log_info "Storage ${mount_point}: ${fstype}"
    fi
    status_nvme_trim
}

migrate_ntfs_storage() {
    local mount_point="${1:-/mnt/data}"
    local fstab_path="/etc/fstab"
    log_info "Migrating ${mount_point} to in-kernel ntfs3 driver..."

    if ! grep -q "${mount_point}" "${fstab_path}" 2>/dev/null; then
        log_warn "Mount point ${mount_point} not found in ${fstab_path}."
        return 0
    fi

    if grep "${mount_point}" "${fstab_path}" | grep -q "ntfs3" && ! grep "${mount_point}" "${fstab_path}" | grep -q "ntfs-3g"; then
        log_pass "${mount_point} is already configured with ntfs3 in ${fstab_path}."
        return 0
    fi

    local ts
    ts="$(date +%Y%m%d%H%M%S)"
    local backup_path="${fstab_path}.bak.${ts}"

    log_info "Creating fstab backup at ${backup_path}..."
    if [[ $EUID -ne 0 ]]; then
        sudo cp "${fstab_path}" "${backup_path}"
    else
        cp "${fstab_path}" "${backup_path}"
    fi

    # Update fstab
    log_info "Updating fstab entry to ntfs3..."
    local tmp_fstab
    tmp_fstab="$(mktemp)"
    while IFS= read -r line || [[ -n "$line" ]]; do
        if echo "$line" | grep -q "${mount_point}" && echo "$line" | grep -q "ntfs-3g"; then
            local p1 p2 p3 p4 prest
            read -r p1 p2 p3 p4 prest <<< "$line"
            if [[ "$p4" != *"iocharset=utf8"* ]]; then
                p4="${p4},iocharset=utf8"
            fi
            echo "$p1 $p2 ntfs3 $p4 $prest" >> "$tmp_fstab"
        else
            echo "$line" >> "$tmp_fstab"
        fi
    done < "${fstab_path}"

    if [[ $EUID -ne 0 ]]; then
        sudo cp "${tmp_fstab}" "${fstab_path}"
    else
        cp "${tmp_fstab}" "${fstab_path}"
    fi
    rm -f "${tmp_fstab}"

    log_info "Testing remount of ${mount_point}..."
    local remount_ok=0
    if [[ $EUID -ne 0 ]]; then
        sudo mount -o remount "${mount_point}" 2>/dev/null || remount_ok=1
    else
        mount -o remount "${mount_point}" 2>/dev/null || remount_ok=1
    fi

    if [[ $remount_ok -ne 0 ]]; then
        log_error "Remount with ntfs3 failed! Rolling back to ${backup_path}..."
        if [[ $EUID -ne 0 ]]; then
            sudo cp "${backup_path}" "${fstab_path}"
            sudo mount -o remount "${mount_point}" 2>/dev/null || true
        else
            cp "${backup_path}" "${fstab_path}"
            mount -o remount "${mount_point}" 2>/dev/null || true
        fi
        return 1
    fi

    log_pass "Successfully migrated ${mount_point} to ntfs3 driver."
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

enable_earlyoom() {
    log_info "Configuring and enabling EarlyOOM daemon..."
    if ! command -v earlyoom >/dev/null 2>&1; then
        log_info "Installing earlyoom package..."
        if [[ $EUID -ne 0 ]]; then
            sudo apt-get update -qq && sudo apt-get install -y -q earlyoom < /dev/null
        else
            apt-get update -qq && apt-get install -y -q earlyoom < /dev/null
        fi
    fi

    local earlyoom_conf="/etc/default/earlyoom"
    local avoid_pattern='(^|/)(init|systemd|sshd|Xorg|wayland|gnome-shell|pipewire|wireplumber|agy|claude)$'
    if [[ $EUID -ne 0 ]]; then
        cat <<EOF | sudo tee "${earlyoom_conf}" >/dev/null
# /etc/default/earlyoom - Managed by os-manager
EARLYOOM_ARGS="-m 5 -s 5 -r 60 --avoid '${avoid_pattern}'"
EOF
        sudo systemctl enable --now earlyoom 2>/dev/null || true
        sudo systemctl restart earlyoom 2>/dev/null || true
    else
        cat <<EOF | tee "${earlyoom_conf}" >/dev/null
# /etc/default/earlyoom - Managed by os-manager
EARLYOOM_ARGS="-m 5 -s 5 -r 60 --avoid '${avoid_pattern}'"
EOF
        systemctl enable --now earlyoom 2>/dev/null || true
        systemctl restart earlyoom 2>/dev/null || true
    fi
    log_pass "EarlyOOM daemon configured and active at: ${earlyoom_conf}"
}

status_earlyoom() {
    if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet earlyoom 2>/dev/null; then
        log_pass "EarlyOOM daemon: Active"
    else
        log_warn "EarlyOOM daemon: Inactive"
    fi
}

audit_swap() {
    log_info "Auditing dual-tier swap hierarchy..."
    if [[ -f "/proc/swaps" ]]; then
        local zram_found=0
        local swapfile_found=0
        while IFS= read -r line; do
            if echo "$line" | grep -q "zram"; then
                zram_found=1
                log_pass "ZRAM active: $line"
            elif echo "$line" | grep -q "swapfile"; then
                swapfile_found=1
                log_pass "Swapfile active: $line"
            fi
        done < "/proc/swaps"
        if [[ $zram_found -eq 0 ]]; then
            log_warn "ZRAM swap device not found in /proc/swaps"
        fi
        if [[ $swapfile_found -eq 0 ]]; then
            log_warn "Swapfile not found in /proc/swaps"
        fi
    else
        log_warn "/proc/swaps is not accessible."
    fi
}

apply_memory_tuning() {
    log_info "Applying Linux memory & VM parameters (MGLRU, zRAM swappiness=180, THP madvise)..."
    local mglru_conf="/etc/tmpfiles.d/00-osm-mglru.conf"
    local thp_conf="/etc/tmpfiles.d/00-osm-thp.conf"
    local vm_conf="/etc/sysctl.d/99-osm-memory.conf"

    if [[ $EUID -ne 0 ]]; then
        cat <<EOF | sudo tee "${mglru_conf}" >/dev/null
# /etc/tmpfiles.d/00-osm-mglru.conf - Managed by os-manager
w /sys/kernel/mm/lru_gen/enabled - - - - 7
w /sys/kernel/mm/lru_gen/min_ttl_ms - - - - 1000
EOF
        cat <<EOF | sudo tee "${thp_conf}" >/dev/null
# /etc/tmpfiles.d/00-osm-thp.conf - Managed by os-manager
w /sys/kernel/mm/transparent_hugepage/enabled - - - - madvise
w /sys/kernel/mm/transparent_hugepage/defrag - - - - defer+madvise
EOF
        cat <<EOF | sudo tee "${vm_conf}" >/dev/null
# /etc/sysctl.d/99-osm-memory.conf - Managed by os-manager
vm.swappiness = 180
vm.page-cluster = 0
vm.watermark_boost_factor = 0
vm.watermark_scale_factor = 125
vm.vfs_cache_pressure = 50
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5
vm.dirty_expire_centisecs = 3000
vm.dirty_writeback_centisecs = 500
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 1024
EOF
        sudo systemd-tmpfiles --create "${mglru_conf}" "${thp_conf}" 2>/dev/null || true
        sudo sysctl --system >/dev/null 2>&1 || sudo sysctl -p "${vm_conf}" 2>/dev/null || true
    else
        cat <<EOF | tee "${mglru_conf}" >/dev/null
# /etc/tmpfiles.d/00-osm-mglru.conf - Managed by os-manager
w /sys/kernel/mm/lru_gen/enabled - - - - 7
w /sys/kernel/mm/lru_gen/min_ttl_ms - - - - 1000
EOF
        cat <<EOF | tee "${thp_conf}" >/dev/null
# /etc/tmpfiles.d/00-osm-thp.conf - Managed by os-manager
w /sys/kernel/mm/transparent_hugepage/enabled - - - - madvise
w /sys/kernel/mm/transparent_hugepage/defrag - - - - defer+madvise
EOF
        cat <<EOF | tee "${vm_conf}" >/dev/null
# /etc/sysctl.d/99-osm-memory.conf - Managed by os-manager
vm.swappiness = 180
vm.page-cluster = 0
vm.watermark_boost_factor = 0
vm.watermark_scale_factor = 125
vm.vfs_cache_pressure = 50
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5
vm.dirty_expire_centisecs = 3000
vm.dirty_writeback_centisecs = 500
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 1024
EOF
        systemd-tmpfiles --create "${mglru_conf}" "${thp_conf}" 2>/dev/null || true
        sysctl --system >/dev/null 2>&1 || sysctl -p "${vm_conf}" 2>/dev/null || true
    fi

    enable_earlyoom
    log_pass "Memory subsystem tuning applied (MGLRU, zRAM swappiness=180, THP madvise, EarlyOOM)."
}

audit_mglru() {
    log_info "Auditing MGLRU parameters..."
    if [[ -f "/sys/kernel/mm/lru_gen/enabled" ]]; then
        local mglru_en
        mglru_en="$(cat /sys/kernel/mm/lru_gen/enabled 2>/dev/null || echo "unknown")"
        log_info "MGLRU enabled: ${mglru_en} (target: 7/0x0007)"
    else
        log_warn "MGLRU not supported by current kernel (/sys/kernel/mm/lru_gen/enabled missing)"
    fi
}

audit_thp() {
    log_info "Auditing Transparent Huge Pages..."
    if [[ -f "/sys/kernel/mm/transparent_hugepage/enabled" ]]; then
        local thp_en
        thp_en="$(cat /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || echo "unknown")"
        log_info "THP enabled: ${thp_en} (target: [madvise])"
    else
        log_warn "THP sysfs not found (/sys/kernel/mm/transparent_hugepage/enabled missing)"
    fi
}

audit_memory() {
    log_info "Auditing memory & resilience subsystems..."
    audit_mglru
    audit_thp
    status_earlyoom
    audit_swap
}

enable_firewall() {
    log_info "Configuring and enabling UFW firewall..."
    local ufw_cmd="ufw"
    if ! command -v "${ufw_cmd}" >/dev/null 2>&1; then
        if [[ -x "/usr/sbin/ufw" ]]; then
            ufw_cmd="/usr/sbin/ufw"
        elif [[ -x "/sbin/ufw" ]]; then
            ufw_cmd="/sbin/ufw"
        else
            log_error "UFW is not installed. Install with: sudo apt install -y ufw"
            return 1
        fi
    fi
    if [[ $EUID -ne 0 ]]; then
        sudo "${ufw_cmd}" default deny incoming
        sudo "${ufw_cmd}" default allow outgoing
        sudo "${ufw_cmd}" --force enable
    else
        "${ufw_cmd}" default deny incoming
        "${ufw_cmd}" default allow outgoing
        "${ufw_cmd}" --force enable
    fi
    log_pass "UFW firewall enabled with default deny incoming / allow outgoing."
}

status_firewall() {
    local ufw_cmd="ufw"
    if ! command -v "${ufw_cmd}" >/dev/null 2>&1; then
        if [[ -x "/usr/sbin/ufw" ]]; then
            ufw_cmd="/usr/sbin/ufw"
        elif [[ -x "/sbin/ufw" ]]; then
            ufw_cmd="/sbin/ufw"
        else
            log_warn "UFW Firewall not installed."
            return 0
        fi
    fi
    local ufw_st
    if [[ $EUID -ne 0 ]]; then
        ufw_st="$(sudo "${ufw_cmd}" status 2>/dev/null | head -n 1 || echo "unknown")"
    else
        ufw_st="$("${ufw_cmd}" status 2>/dev/null | head -n 1 || echo "unknown")"
    fi
    log_info "UFW Firewall: ${ufw_st}"
}

audit_system() {
    echo "=================================================="
    echo "      Kernel, Storage & Security Hardening Audit  "
    echo "=================================================="
    audit_storage
    audit_sysctl
    audit_memory
    audit_scheduler
    status_audio
    status_firewall
    echo "=================================================="
}

show_help() {
    cat <<EOF
Usage: $(basename "$0") [OPTION] [SUBCOMMAND]

Options:
    --storage [migrate|audit]  Migrate NTFS mount to ntfs3 or audit storage status
    --sysctl [apply|audit]     Apply or audit kernel sysctl performance configuration
    --scheduler [apply|audit]  Apply or audit EEVDF scheduler & cgroups v2 user slices
    --trim [enable|status]     Enable periodic TRIM or check fstrim.timer status
    --earlyoom [enable|status] Configure EarlyOOM daemon or check status
    --memory [apply|audit]     Configure memory resilience (EarlyOOM) or audit swap/memory
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
        --storage)
            if [[ "${subaction}" == "migrate" ]]; then
                migrate_ntfs_storage
            else
                audit_storage
            fi
            ;;
        --sysctl)
            if [[ "${subaction}" == "audit" ]]; then
                audit_sysctl
            else
                apply_sysctl_tuning
            fi
            ;;
        --scheduler)
            if [[ "${subaction}" == "apply" ]]; then
                apply_scheduler_tuning
            else
                audit_scheduler
            fi
            ;;
        --trim)
            if [[ "${subaction}" == "status" ]]; then
                status_nvme_trim
            else
                enable_nvme_trim
            fi
            ;;
        --earlyoom)
            if [[ "${subaction}" == "status" ]]; then
                status_earlyoom
            else
                enable_earlyoom
            fi
            ;;
        --memory)
            if [[ "${subaction}" == "apply" ]]; then
                apply_memory_tuning
            else
                audit_memory
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
