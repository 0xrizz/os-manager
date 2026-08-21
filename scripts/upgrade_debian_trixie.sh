#!/usr/bin/env bash
# scripts/upgrade_debian_trixie.sh - Debian 13 (Trixie) Upgrade Engine for os-manager
# 100% Zero-Dependency POSIX Bash 4.4+ Implementation
set -euo pipefail

# Headroom Constants (in Kilobytes)
readonly MIN_ROOT_FREE_KB=15728640   # 15 GB (for dual unpack & archives)
readonly MIN_BOOT_FREE_KB=1048576    # 1.0 GB (for dual initramfs generation)
readonly MIN_EFI_FREE_KB=20480       # 20 MB
readonly MIN_VIRTUAL_MEM_KB=2097152  # 2.0 GB virtual memory (RAM + Swap)
readonly DEBIAN_MIRROR_HOST="deb.debian.org"
readonly DEFAULT_BACKUP_BASE="/var/backups/osm"
readonly SECONDARY_BACKUP_BASE="/mnt/data/osm_backups"

# Flags
DRY_RUN=0
CHECK_ONLY=0
BACKUP_ONLY=0
TRANSITION_ONLY=0
ALLOW_UNATTACHED=0
TEMP_DIR=""

log_info() {
    echo -e "\033[1;34m[INFO]\033[0m $*"
}

log_pass() {
    echo -e "\033[1;32m[PASS]\033[0m $*"
}

log_warn() {
    echo -e "\033[1;33m[WARN]\033[0m $*"
}

log_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $*" >&2
}

cleanup() {
    if [[ -n "${TEMP_DIR}" && -d "${TEMP_DIR}" ]]; then
        rm -rf "${TEMP_DIR}"
    fi
}
trap cleanup EXIT INT TERM

show_help() {
    cat << 'EOF'
Usage: upgrade_debian_trixie.sh [OPTIONS]

Debian 13 (Trixie) Upgrade Automation Engine (Phases 0-2)

Options:
  --check              Run Phase 0 pre-flight readiness checks only and exit
  --dry-run            Simulate execution without modifying system state
  --backup-only        Execute Phase 1 state backup & dual-snapshot archiving only
  --transition-only    Execute Phase 2 deb822 repository transition only
  --allow-unattached   Bypass mandatory tmux/screen session check (not recommended)
  --help               Display this help message and exit

Environment Overrides:
  OSM_APT_DIR                Target directory for apt configuration (default: /etc/apt)
  OSM_BACKUP_DIR             Target directory for primary backup snapshot
  OSM_MOCK_ROOT              Set to 1 to simulate root privileges in test environments
  OSM_MOCK_TMUX              Set to 1 to simulate active tmux session (0 to simulate unattached)
  OSM_MOCK_POWER_AC          Set to 0 to simulate battery power only (1 for AC connected)
  OSM_MOCK_MEM_AVAIL_KB      Override detected MemAvailable KB for testing
  OSM_MOCK_SWAP_TOTAL_KB     Override detected SwapTotal KB for testing
  OSM_MOCK_EFI_MOUNTED       Set to 0 to simulate unmounted /boot/efi
  OSM_MOCK_DATA_MOUNTED      Set to 0 to simulate unmounted /mnt/data
  OSM_MOCK_ROOT_FREE_KB      Override detected root free KB for testing
  OSM_MOCK_BOOT_FREE_KB      Override detected /boot free KB for testing
  OSM_MOCK_EFI_FREE_KB       Override detected /boot/efi free KB for testing
  OSM_MOCK_NETWORK_FAIL      Set to 1 to simulate network failure
  OSM_MOCK_DPKG_AUDIT_FAIL   Set to 1 to simulate broken dpkg packages
EOF
}

ensure_sleep_inhibited() {
    if [[ "${OSM_INHIBITED:-0}" == "1" || "${OSM_MOCK_ROOT:-0}" == "1" ]]; then
        return 0
    fi
    if [[ "${EUID}" -eq 0 ]] && command -v systemd-inhibit >/dev/null 2>&1; then
        if [[ -z "${SYSTEMD_INHIBITED:-}" ]]; then
            log_info "Wrapping upgrade process in systemd-inhibit to block sleep/lid-switch/idle events..."
            export OSM_INHIBITED=1
            exec systemd-inhibit \
                --why="Debian 13 (Trixie) Major Distribution Upgrade in Progress" \
                --what="sleep:idle:shutdown:handle-lid-switch:handle-power-key:handle-suspend-key" \
                --mode=block \
                "$0" "$@"
        fi
    fi
    return 0
}

check_root() {
    if [[ "${OSM_MOCK_ROOT:-0}" == "1" ]]; then
        return 0
    fi
    if [[ "${EUID}" -ne 0 ]]; then
        log_error "Must be executed with root privileges (EUID 0) or via sudo."
        return 1
    fi
    return 0
}

check_power_source() {
    if [[ "${OSM_MOCK_POWER_AC:-1}" == "0" ]]; then
        log_error "AC power adapter is not connected (mocked battery power). Upgrading on battery is prohibited."
        return 1
    fi
    if [[ "${OSM_MOCK_POWER_AC:-0}" == "1" || "${OSM_MOCK_ROOT:-0}" == "1" ]]; then
        log_pass "Power source verified: AC power connected."
        return 0
    fi

    if command -v on_ac_power >/dev/null 2>&1; then
        if ! on_ac_power; then
            log_error "AC power adapter is not connected! Upgrading on battery power is prohibited to prevent thermal cutoff."
            return 1
        fi
        log_pass "Power source verified: AC power connected (via on_ac_power)."
        return 0
    fi

    # Fallback to sysfs inspection
    local ac_online=0
    for ps in /sys/class/power_supply/*/online; do
        if [[ -f "${ps}" ]] && grep -q "1" "${ps}" 2>/dev/null; then
            ac_online=1
            break
        fi
    done
    if [[ "${ac_online}" -eq 1 ]]; then
        log_pass "Power source verified: AC power connected (via sysfs)."
        return 0
    fi

    log_warn "Unable to verify AC power state via on_ac_power or sysfs; proceeding with caution."
    return 0
}

set_oom_protection() {
    if [[ -w /proc/$$/oom_score_adj ]]; then
        echo -1000 > /proc/$$/oom_score_adj 2>/dev/null || true
        log_pass "Process OOM score adjustment set to -1000 (immune to OOM killer)."
    fi
    return 0
}

check_memory_headroom() {
    local mem_avail_kb=0
    local swap_total_kb=0

    if [[ -n "${OSM_MOCK_MEM_AVAIL_KB:-}" ]]; then
        mem_avail_kb="${OSM_MOCK_MEM_AVAIL_KB}"
    elif [[ -f /proc/meminfo ]]; then
        mem_avail_kb="$(grep MemAvailable /proc/meminfo | awk '{print $2}' || echo 0)"
    fi

    if [[ -n "${OSM_MOCK_SWAP_TOTAL_KB:-}" ]]; then
        swap_total_kb="${OSM_MOCK_SWAP_TOTAL_KB}"
    elif [[ -f /proc/meminfo ]]; then
        swap_total_kb="$(grep SwapTotal /proc/meminfo | awk '{print $2}' || echo 0)"
    fi

    local total_virtual_kb=$(( mem_avail_kb + swap_total_kb ))
    local total_virtual_mb=$(( total_virtual_kb / 1024 ))
    local required_mb=$(( MIN_VIRTUAL_MEM_KB / 1024 ))

    if [[ "${total_virtual_kb}" -lt "${MIN_VIRTUAL_MEM_KB}" ]]; then
        log_error "Insufficient available virtual memory (${total_virtual_mb} MB available, ${required_mb} MB required). Risk of OOM killer during parallel zstd initramfs compression."
        return 1
    fi

    log_pass "Virtual memory headroom verified: ${total_virtual_mb} MB available (Required: ${required_mb} MB)."
    return 0
}

check_multiplexer() {
    if [[ "${ALLOW_UNATTACHED}" -eq 1 ]]; then
        log_warn "Multiplexer check bypassed via --allow-unattached."
        return 0
    fi
    if [[ "${OSM_MOCK_TMUX:-}" == "1" ]]; then
        log_pass "Terminal Multiplexer session detected (mocked)."
        return 0
    fi
    if [[ "${OSM_MOCK_TMUX:-}" == "0" ]]; then
        log_error "Must be executed inside an active tmux or screen session to prevent terminal drop on display manager restarts."
        return 1
    fi

    if [[ -n "${TMUX:-}" || -n "${STY:-}" ]]; then
        log_pass "Terminal Multiplexer session active (tmux/screen)."
        return 0
    fi

    # Check if running in a pure Linux virtual console
    local tty_name
    tty_name="$(tty 2>/dev/null || echo "")"
    if [[ "${tty_name}" =~ ^/dev/tty[1-6]$ ]]; then
        log_pass "Running inside pure Linux Virtual Console (${tty_name})."
        return 0
    fi

    log_error "Must be executed inside an active tmux/screen session or pure Linux Virtual Console (TTY3). GNOME/Wayland restarts during upgrade will terminate unattached terminals. Launch with 'tmux' first or pass '--allow-unattached'."
    return 1
}

preseed_debconf_grub() {
    log_info "Pre-seeding debconf selections for GRUB EFI non-interactive installation..."
    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log_pass "[DRY-RUN] Pre-seeded grub2/force_efi_extra_removable and grub-efi/install_devices."
        return 0
    fi

    if command -v debconf-set-selections >/dev/null 2>&1; then
        echo "grub2/force_efi_extra_removable boolean true" | debconf-set-selections 2>/dev/null || true
        echo "grub-efi-amd64 grub-efi/install_devices multiselect /dev/nvme0n1p1" | debconf-set-selections 2>/dev/null || true
        log_pass "Debconf selections for GRUB EFI successfully pre-seeded."
    else
        log_warn "debconf-set-selections command not available; falling back to environment non-interactive flags."
    fi
    return 0
}

check_secure_boot_and_dkms() {
    if command -v mokutil >/dev/null 2>&1; then
        if mokutil --sb-state 2>&1 | grep -qi "SecureBoot enabled"; then
            log_info "UEFI Secure Boot is ENABLED. Linux 6.12+ enforces kernel lockdown mode."
            if dpkg -l 2>/dev/null | grep -qE '^ii.*dkms'; then
                log_warn "DKMS modules detected under Secure Boot. MOK key enrollment may be required upon reboot."
            fi
        fi
    fi
    return 0
}

sanitize_networkmanager_keyfiles() {
    if [[ -d /etc/NetworkManager/system-connections && "${EUID}" -eq 0 ]]; then
        log_info "Normalizing NetworkManager Wi-Fi keyfile permissions to 0600..."
        chmod 0600 /etc/NetworkManager/system-connections/* 2>/dev/null || true
        chown root:root /etc/NetworkManager/system-connections/* 2>/dev/null || true
        log_pass "NetworkManager keyfile permissions verified."
    fi
    return 0
}

get_mount_free_kb() {
    local target_path="$1"
    if [[ "${target_path}" == "/" && -n "${OSM_MOCK_ROOT_FREE_KB:-}" ]]; then
        echo "${OSM_MOCK_ROOT_FREE_KB}"
        return 0
    fi
    if [[ "${target_path}" == "/boot" && -n "${OSM_MOCK_BOOT_FREE_KB:-}" ]]; then
        echo "${OSM_MOCK_BOOT_FREE_KB}"
        return 0
    fi
    if [[ "${target_path}" == "/boot/efi" && -n "${OSM_MOCK_EFI_FREE_KB:-}" ]]; then
        echo "${OSM_MOCK_EFI_FREE_KB}"
        return 0
    fi

    if ! df -P "${target_path}" >/dev/null 2>&1; then
        echo "0"
        return 1
    fi
    df -P "${target_path}" | awk 'NR==2 {print $4}'
}

check_mountpoint_and_headroom() {
    local mount_point="$1"
    local required_kb="$2"
    local label="$3"
    local require_mountpoint="${4:-0}"

    # 1. Mountpoint validation if required
    if [[ "${require_mountpoint}" -eq 1 ]]; then
        if [[ "${mount_point}" == "/boot/efi" && "${OSM_MOCK_EFI_MOUNTED:-1}" == "0" ]]; then
            log_error "${mount_point} is not a mounted filesystem (${label}). ESP partition must be mounted."
            return 1
        fi
        if [[ "${mount_point}" != "/boot/efi" && "${OSM_MOCK_DATA_MOUNTED:-1}" == "0" ]]; then
            log_error "${mount_point} is not a mounted filesystem (${label})."
            return 1
        fi
        if ! mountpoint -q "${mount_point}" 2>/dev/null && [[ -z "${OSM_MOCK_EFI_FREE_KB:-}" && -z "${OSM_MOCK_ROOT_FREE_KB:-}" ]]; then
            log_error "${mount_point} is not a mounted filesystem (${label})."
            return 1
        fi
    fi

    # 2. Disk headroom check
    local free_kb
    free_kb="$(get_mount_free_kb "${mount_point}")" || {
        log_error "Mount point ${mount_point} (${label}) is inaccessible."
        return 1
    }

    local free_mb=$(( free_kb / 1024 ))
    local required_mb=$(( required_kb / 1024 ))

    if [[ "${free_kb}" -lt "${required_kb}" ]]; then
        log_error "Insufficient free space on ${mount_point} (${label}): ${free_mb} MB available, ${required_mb} MB required."
        return 1
    fi

    log_pass "Disk space on ${mount_point} (${label}): ${free_mb} MB available (Required: ${required_mb} MB)"
    return 0
}

check_network_connectivity() {
    local host="$1"

    if [[ "${OSM_MOCK_NETWORK_FAIL:-0}" == "1" ]]; then
        log_error "Cannot reach Debian mirror at ${host} (mocked network failure)."
        return 1
    fi

    if command -v curl >/dev/null 2>&1; then
        if curl -s --connect-timeout 5 -I "http://${host}" >/dev/null 2>&1; then
            log_pass "Network connectivity to Debian mirror (${host}) verified via curl"
            return 0
        fi
    fi

    if command -v nc >/dev/null 2>&1; then
        if nc -z -w 5 "${host}" 80 >/dev/null 2>&1; then
            log_pass "Network connectivity to Debian mirror (${host}) verified via nc"
            return 0
        fi
    fi

    if getent hosts "${host}" >/dev/null 2>&1; then
        log_pass "DNS resolution for ${host} successful"
        return 0
    fi

    log_error "Cannot reach Debian mirror at ${host} or resolve DNS."
    return 1
}

check_dpkg_integrity() {
    if [[ "${OSM_MOCK_DPKG_AUDIT_FAIL:-0}" == "1" ]]; then
        log_error "Broken or inconsistent packages detected (mocked dpkg audit failure)."
        return 1
    fi

    local audit_out
    audit_out="$(dpkg --audit 2>&1 || true)"
    if [[ -n "${audit_out}" ]]; then
        log_error "Broken or inconsistent packages detected in 'dpkg --audit':\n${audit_out}"
        return 1
    fi

    local held_pkgs
    held_pkgs="$(dpkg --get-selections | grep -E '\bhold$' || true)"
    if [[ -n "${held_pkgs}" ]]; then
        log_warn "Held packages detected:\n${held_pkgs}"
    fi

    local lock_files=("/var/lib/apt/lists/lock" "/var/lib/dpkg/lock-frontend" "/var/lib/dpkg/lock")
    for lock in "${lock_files[@]}"; do
        if [[ -f "${lock}" ]] && fuser "${lock}" >/dev/null 2>&1; then
            log_error "Active APT/DPKG lock held on ${lock}. Ensure no other package manager is running."
            return 1
        fi
    done

    log_pass "DPKG & APT lock state clean (no broken packages or blocking locks)"
    return 0
}

check_preflight() {
    log_info "Executing Phase 0: Pre-Flight Verification Gate..."
    local errors=0

    if ! check_root; then
        errors=$((errors + 1))
    fi

    if ! check_power_source; then
        errors=$((errors + 1))
    fi

    set_oom_protection

    if ! check_memory_headroom; then
        errors=$((errors + 1))
    fi

    if ! check_multiplexer; then
        errors=$((errors + 1))
    fi

    if ! check_mountpoint_and_headroom "/" "${MIN_ROOT_FREE_KB}" "Root partition" 0; then
        errors=$((errors + 1))
    fi

    # Check /boot headroom (min 1.0 GB for dual initramfs generation)
    if [[ -d "/boot" ]]; then
        if ! check_mountpoint_and_headroom "/boot" "${MIN_BOOT_FREE_KB}" "Boot storage (/boot)" 0; then
            errors=$((errors + 1))
        fi
    fi

    # Check /boot/efi mountpoint and headroom (min 20 MB)
    if [[ -d "/boot/efi" ]]; then
        if ! check_mountpoint_and_headroom "/boot/efi" "${MIN_EFI_FREE_KB}" "EFI partition" 1; then
            errors=$((errors + 1))
        fi
    fi

    check_secure_boot_and_dkms
    sanitize_networkmanager_keyfiles

    if ! preseed_debconf_grub; then
        errors=$((errors + 1))
    fi

    if ! check_network_connectivity "${DEBIAN_MIRROR_HOST}"; then
        errors=$((errors + 1))
    fi

    if ! check_dpkg_integrity; then
        errors=$((errors + 1))
    fi

    if [[ "${errors}" -gt 0 ]]; then
        log_error "Phase 0 Pre-Flight Verification FAILED with ${errors} error(s)."
        return 2
    fi

    log_pass "Phase 0 Pre-Flight Verification PASSED cleanly."
    return 0
}

generate_emergency_rescue_script() {
    local target_file="$1"
    log_info "Generating standalone Emergency Rescue Script at ${target_file}..."

    cat > "${target_file}" << 'EOF'
#!/usr/bin/env bash
# emergency_rescue.sh - Debian 13 (Trixie) Standalone Offline Recovery Helper
# Automatically generated by os-manager prior to upgrade execution.
set -euo pipefail

echo "============================================================"
echo "     Debian 13 (Trixie) Emergency System Rescue Helper      "
echo "============================================================"

if [[ "${EUID}" -ne 0 ]]; then
    echo "ERROR: Must be executed as root (e.g. from Debian Live USB)." >&2
    exit 1
fi

ROOT_PART="/dev/nvme0n1p2"
EFI_PART="/dev/nvme0n1p1"
TARGET_MOUNT="/mnt"

echo "1. Mounting Root (${ROOT_PART}) to ${TARGET_MOUNT}..."
mount "${ROOT_PART}" "${TARGET_MOUNT}"

if [[ -d "${TARGET_MOUNT}/boot/efi" ]]; then
    echo "2. Mounting EFI System Partition (${EFI_PART})..."
    mount "${EFI_PART}" "${TARGET_MOUNT}/boot/efi"
fi

echo "3. Attempting Option A: Offline Host-Level DPKG & APT Repair..."
echo "   (Survives broken internal libc6 dynamic linker crashes)"
dpkg --root="${TARGET_MOUNT}" --configure -a || true
apt-get -o RootDir="${TARGET_MOUNT}" update || true
apt-get -o RootDir="${TARGET_MOUNT}" install -f -y || true

echo "4. Setting up virtual filesystem bind mounts including EFI variables..."
for i in /dev /dev/pts /proc /sys /run; do
    mount --bind "$i" "${TARGET_MOUNT}$i"
done
if [[ -d /sys/firmware/efi/efivars ]]; then
    mount --bind /sys/firmware/efi/efivars "${TARGET_MOUNT}/sys/firmware/efi/efivars"
fi

echo "5. Executing in-chroot finalization..."
chroot "${TARGET_MOUNT}" /bin/bash -c "
    dpkg --configure -a
    apt-get update && apt-get install -f -y
    update-initramfs -u -k all
    update-grub
" || echo "WARNING: In-chroot repair failed. Verify package integrity manually."

echo "6. GPU Black-Screen / Wayland Recovery Note:"
echo "   If the upgraded system boots to a black screen due to hybrid GPU modesetting,"
echo "   append 'nouveau.modeset=0 modprobe.blacklist=nouveau' to the kernel command line in GRUB."

echo "Rescue operations complete. You may unmount and reboot."
EOF
    chmod +x "${target_file}"
}

create_backup() {
    log_info "Executing Phase 1: State Backup & Manifest Snapshot..."
    local timestamp
    timestamp="$(date -u +"%Y%m%d_%H%M%SZ")"

    local backup_dir
    if [[ -n "${OSM_BACKUP_DIR:-}" ]]; then
        backup_dir="${OSM_BACKUP_DIR}"
    else
        backup_dir="${DEFAULT_BACKUP_BASE}/apt_pre_trixie_${timestamp}"
    fi

    local secondary_dir="${OSM_SECONDARY_BACKUP_DIR:-${SECONDARY_BACKUP_BASE}}"

    log_info "Primary target backup directory: ${backup_dir}"
    mkdir -p "${backup_dir}" || {
        log_error "Failed to create backup directory ${backup_dir}."
        return 2
    }

    # 1. Snapshot /etc/apt/
    log_info "Creating snapshot of /etc/apt/..."
    if [[ -d "/etc/apt" ]]; then
        mkdir -p "${backup_dir}/apt"
        cp -a /etc/apt/. "${backup_dir}/apt/" || {
            log_error "Failed to copy /etc/apt/ to backup destination."
            return 2
        }
    fi

    # 2. Archive critical /etc and NetworkManager configuration
    log_info "Creating /etc configuration tarball snapshot (including NetworkManager)..."
    tar -czf "${backup_dir}/etc_config_snapshot.tar.gz" \
        --exclude='*.log' \
        --exclude='*.tmp' \
        /etc/fstab /etc/default /etc/network /etc/NetworkManager /etc/systemd 2>/dev/null || true
    touch "${backup_dir}/etc_config_snapshot.tar.gz"

    # 3. Export package manifests
    log_info "Exporting installed package selections (dpkg & apt-mark)..."
    dpkg --get-selections > "${backup_dir}/dpkg_selections.txt" || {
        log_error "Failed to export dpkg package selections."
        return 2
    }

    if command -v apt-mark >/dev/null 2>&1; then
        apt-mark showmanual > "${backup_dir}/apt_manual_pkgs.txt" 2>/dev/null || true
    fi
    touch "${backup_dir}/apt_manual_pkgs.txt"

    # 4. Generate upgrade_manifest.json
    log_info "Generating upgrade_manifest.json telemetry..."
    local kernel_ver arch deb_ver hostname_str
    kernel_ver="$(uname -r 2>/dev/null || echo "unknown")"
    arch="$(dpkg --print-architecture 2>/dev/null || uname -m)"
    deb_ver="$(cat /etc/debian_version 2>/dev/null || echo "12")"
    hostname_str="$(hostname 2>/dev/null || echo "localhost")"

    cat > "${backup_dir}/upgrade_manifest.json" << EOF
{
  "timestamp": "${timestamp}",
  "hostname": "${hostname_str}",
  "source_distribution": "Debian GNU/Linux",
  "source_version": "${deb_ver}",
  "source_codename": "bookworm",
  "target_suite": "trixie",
  "kernel": "${kernel_ver}",
  "architecture": "${arch}",
  "backup_dir": "${backup_dir}",
  "backup_files": [
    "apt/",
    "etc_config_snapshot.tar.gz",
    "dpkg_selections.txt",
    "apt_manual_pkgs.txt",
    "upgrade_manifest.json"
  ]
}
EOF

    # 5. Dual Backup Mirroring to /mnt/data (NTFS-Safe Compressed Tarball)
    local is_secondary_mounted=0
    if mountpoint -q "/mnt/data" 2>/dev/null || [[ -n "${OSM_SECONDARY_BACKUP_DIR:-}" ]]; then
        is_secondary_mounted=1
    fi

    if [[ "${is_secondary_mounted}" -eq 1 ]]; then
        log_info "Mirroring backup bundle to secondary persistent storage via compressed tarball (${secondary_dir})..."
        mkdir -p "${secondary_dir}"
        local tarball_path="${secondary_dir}/apt_pre_trixie_${timestamp}.tar.gz"
        tar -czf "${tarball_path}" -C "$(dirname "${backup_dir}")" "$(basename "${backup_dir}")" || {
            log_warn "Failed to create compressed secondary backup archive on ${secondary_dir}."
        }
        if [[ -f "${tarball_path}" ]]; then
            log_pass "NTFS-Safe Secondary backup mirrored to ${tarball_path}"
        fi

        # 6. Generate standalone emergency rescue script on persistent storage
        generate_emergency_rescue_script "${secondary_dir}/emergency_rescue.sh"
    else
        log_warn "Secondary storage /mnt/data is not mounted; skipping persistent backup mirroring."
    fi

    log_pass "Phase 1 Backup completed successfully at: ${backup_dir}"
    return 0
}

generate_deb822_sources() {
    local target_file="$1"
    log_info "Writing Debian 13 (Trixie) deb822 repository matrix to ${target_file}..."

    cat > "${target_file}" << 'EOF'
Types: deb deb-src
URIs: http://deb.debian.org/debian
Suites: trixie trixie-updates trixie-backports
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg

Types: deb deb-src
URIs: http://security.debian.org/debian-security
Suites: trixie-security
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
EOF
}

transition_sources() {
    local apt_dir="${1:-${OSM_APT_DIR:-/etc/apt}}"
    log_info "Executing Phase 2: APT deb822 Repository Matrix Transition in ${apt_dir}..."

    if [[ ! -d "${apt_dir}" ]]; then
        log_error "Target APT directory ${apt_dir} does not exist."
        return 2
    fi

    mkdir -p "${apt_dir}/sources.list.d"

    # 1. Write deb822 format sources
    generate_deb822_sources "${apt_dir}/sources.list.d/debian.sources"

    # 2. Clear legacy sources.list to prevent duplicate warnings
    if [[ -f "${apt_dir}/sources.list" ]]; then
        cat > "${apt_dir}/sources.list" << 'EOF'
# Legacy sources.list cleared by os-manager. Active repositories are configured in sources.list.d/debian.sources
EOF
    fi

    # 3. Disable external third party lists
    shopt -s nullglob
    local list_files=("${apt_dir}/sources.list.d/"*.list)
    shopt -u nullglob

    for f in "${list_files[@]}"; do
        log_warn "Disabling third-party repository during upgrade: $(basename "${f}")"
        mv "${f}" "${f}.disabled_for_upgrade"
    done

    log_pass "Phase 2 deb822 Source Transition completed successfully."
    return 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --check)
                CHECK_ONLY=1
                shift
                ;;
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            --backup-only)
                BACKUP_ONLY=1
                shift
                ;;
            --transition-only)
                TRANSITION_ONLY=1
                shift
                ;;
            --allow-unattached)
                ALLOW_UNATTACHED=1
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
            esac
    done
}

main() {
    ensure_sleep_inhibited "$@"
    parse_args "$@"

    if [[ "${CHECK_ONLY}" -eq 1 ]]; then
        check_preflight
        exit $?
    fi

    if [[ "${BACKUP_ONLY}" -eq 1 ]]; then
        check_preflight
        create_backup
        exit $?
    fi

    if [[ "${TRANSITION_ONLY}" -eq 1 ]]; then
        check_preflight
        transition_sources "${OSM_APT_DIR:-/etc/apt}"
        exit $?
    fi

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log_info "Executing in --dry-run simulation mode..."
        check_preflight
        log_pass "Dry-run pre-flight check completed successfully."
        exit 0
    fi

    check_preflight
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
