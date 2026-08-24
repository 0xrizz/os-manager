#!/usr/bin/env bash
# scripts/tune_hardware.sh - Lenovo ACPI, Thermals, GPU Power Gating, and VA-API Tuning
set -euo pipefail

SYSFS_CONSERVATION_DEFAULT="/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode"
SYSFS_PROFILE_DEFAULT="/sys/firmware/acpi/platform_profile"
SYSFS_PROFILE_CHOICES_DEFAULT="/sys/firmware/acpi/platform_profile_choices"
SYSFS_FN_LOCK_DEFAULT="/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/fn_lock"
SYSFS_GPU_DEFAULT="/sys/bus/pci/devices/0000:01:00.0/power"
PERSIST_SERVICE="/etc/systemd/system/osm-hardware-tune.service"
PERSIST_CONF_DIR="/etc/osm"
PERSIST_CONF="${PERSIST_CONF_DIR}/hardware-tune.conf"

log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_pass()  { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; }

get_battery_status() {
    local path="${1:-${SYSFS_CONSERVATION_DEFAULT}}"
    if [[ ! -f "${path}" ]]; then
        echo "unsupported"
        return 0
    fi
    local val
    val="$(cat "${path}" 2>/dev/null || echo "0")"
    if [[ "${val}" == "1" ]]; then
        echo "enabled"
    else
        echo "disabled"
    fi
}

set_battery_conservation() {
    local state="$1"
    local path="${2:-${SYSFS_CONSERVATION_DEFAULT}}"
    local target_val="1"

    if [[ "${state}" == "off" || "${state}" == "disable" || "${state}" == "0" ]]; then
        target_val="0"
    fi

    if [[ ! -f "${path}" ]]; then
        log_error "Lenovo Conservation Mode sysfs node not found at: ${path}"
        return 1
    fi

    echo "${target_val}" | tee "${path}" >/dev/null
    log_pass "Lenovo Battery Conservation Mode set to: $(get_battery_status "${path}")"
    return 0
}

get_platform_profile() {
    local path="${1:-${SYSFS_PROFILE_DEFAULT}}"
    if [[ ! -f "${path}" ]]; then
        echo "unsupported"
        return 0
    fi
    cat "${path}" 2>/dev/null || echo "unsupported"
}

set_platform_profile() {
    local prof="$1"
    local path="${2:-${SYSFS_PROFILE_DEFAULT}}"
    local choices_path="${3:-${SYSFS_PROFILE_CHOICES_DEFAULT}}"

    if [[ "${prof}" == "quiet" ]]; then
        prof="low-power"
    fi

    if [[ ! -f "${path}" ]]; then
        log_error "ACPI platform_profile node not found at: ${path}"
        return 1
    fi

    if [[ -f "${choices_path}" ]]; then
        local choices
        choices="$(cat "${choices_path}")"
        if [[ ! " ${choices} " =~ " ${prof} " ]]; then
            log_error "Unsupported profile '${prof}'. Supported choices: ${choices}"
            return 1
        fi
    fi

    echo "${prof}" | tee "${path}" >/dev/null
    log_pass "ACPI platform profile set to: $(get_platform_profile "${path}")"
    return 0
}

get_fn_lock_status() {
    local path="${1:-${SYSFS_FN_LOCK_DEFAULT}}"
    if [[ ! -f "${path}" ]]; then
        echo "unsupported"
        return 0
    fi
    local val
    val="$(cat "${path}" 2>/dev/null || echo "0")"
    if [[ "${val}" == "1" ]]; then
        echo "enabled"
    else
        echo "disabled"
    fi
}

set_fn_lock() {
    local state="$1"
    local path="${2:-${SYSFS_FN_LOCK_DEFAULT}}"
    local target_val="1"

    if [[ "${state}" == "off" || "${state}" == "disable" || "${state}" == "0" ]]; then
        target_val="0"
    fi

    if [[ ! -f "${path}" ]]; then
        log_error "Lenovo Fn-Lock sysfs node not found at: ${path}"
        return 1
    fi

    echo "${target_val}" | tee "${path}" >/dev/null
    log_pass "Lenovo Fn-Lock set to: $(get_fn_lock_status "${path}")"
    return 0
}

audit_gpu_power() {
    local path="${1:-${SYSFS_GPU_DEFAULT}}"
    log_info "Auditing Hybrid NVIDIA GPU Power Gating Status..."
    if [[ ! -d "${path}" ]]; then
        log_warn "Discrete GPU PCI power management node not found at: ${path}"
        return 0
    fi

    local st="unknown"
    local ctrl="unknown"
    [[ -f "${path}/runtime_status" ]] && st="$(cat "${path}/runtime_status")"
    [[ -f "${path}/control" ]] && ctrl="$(cat "${path}/control")"

    if [[ "${st}" == "suspended" ]]; then
        log_pass "NVIDIA dGPU is in Runtime D3 Cold state (suspended, 0W idle draw, control: ${ctrl})"
    else
        log_warn "NVIDIA dGPU is currently ${st} (control: ${ctrl}). Run --gpu power-save to enforce autosuspend."
    fi
}

enforce_gpu_power_save() {
    local path="${1:-${SYSFS_GPU_DEFAULT}}"
    if [[ -f "${path}/control" ]]; then
        echo "auto" | tee "${path}/control" >/dev/null
        log_pass "NVIDIA dGPU power control set to 'auto'."
    else
        log_warn "GPU power control node not found at: ${path}/control"
    fi

    local modprobe_conf="/etc/modprobe.d/nvidia-pm.conf"
    local udev_rule="/etc/udev/rules.d/80-nvidia-pm.rules"
    log_info "Deploying NVIDIA RTD3 dynamic power management and udev rules..."
    if [[ $EUID -ne 0 ]]; then
        cat <<EOF | sudo tee "${modprobe_conf}" >/dev/null
# /etc/modprobe.d/nvidia-pm.conf - Managed by os-manager
options nvidia "NVreg_DynamicPowerManagement=0x02"
EOF
        cat <<EOF | sudo tee "${udev_rule}" >/dev/null
# /etc/udev/rules.d/80-nvidia-pm.rules - Managed by os-manager
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030000", ATTR{power/control}="auto"
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030200", ATTR{power/control}="auto"
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x040300", ATTR{power/control}="auto"
EOF
        sudo udevadm control --reload-rules 2>/dev/null || true
        sudo udevadm trigger 2>/dev/null || true
    else
        cat <<EOF | tee "${modprobe_conf}" >/dev/null
# /etc/modprobe.d/nvidia-pm.conf - Managed by os-manager
options nvidia "NVreg_DynamicPowerManagement=0x02"
EOF
        cat <<EOF | tee "${udev_rule}" >/dev/null
# /etc/udev/rules.d/80-nvidia-pm.rules - Managed by os-manager
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030000", ATTR{power/control}="auto"
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x030200", ATTR{power/control}="auto"
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="0x10de", ATTR{class}=="0x040300", ATTR{power/control}="auto"
EOF
        udevadm control --reload-rules 2>/dev/null || true
        udevadm trigger 2>/dev/null || true
    fi
    log_pass "NVIDIA dynamic PM rules configured at ${modprobe_conf} and ${udev_rule}"
}

audit_vaapi() {
    log_info "Auditing Intel VA-API Hardware Video Acceleration..."
    if ! command -v vainfo >/dev/null 2>&1; then
        log_warn "vainfo utility not installed. Run: sudo apt install -y vainfo intel-media-va-driver-non-free"
        return 1
    fi

    local out
    if out="$(vainfo 2>&1)"; then
        log_pass "VA-API driver initialized successfully:\n${out}"
        return 0
    else
        log_error "VA-API initialization failed:\n${out}"
        return 1
    fi
}

install_vaapi_drivers() {
    log_info "Installing Intel Media VA-API non-free driver packages..."
    apt-get update -q
    apt-get install -y -q intel-media-va-driver-non-free vainfo i965-va-driver-shaders
    log_pass "Intel VA-API media driver installation completed."
}

audit_thermals() {
    log_info "Auditing Intel thermald daemon status..."
    local thermald_cmd="thermald"
    if ! command -v "${thermald_cmd}" >/dev/null 2>&1; then
        if [[ -x "/usr/sbin/thermald" ]]; then
            thermald_cmd="/usr/sbin/thermald"
        elif [[ -x "/sbin/thermald" ]]; then
            thermald_cmd="/sbin/thermald"
        else
            log_warn "thermald is not installed. Run: $0 --thermals install"
            return 1
        fi
    fi
    if systemctl is-active --quiet thermald 2>/dev/null; then
        log_pass "thermald service is active and running."
    else
        log_warn "thermald service is installed but not active."
    fi
}

install_thermals() {
    log_info "Installing Intel thermald package..."
    apt-get update -q
    apt-get install -y -q thermald
    systemctl enable --now thermald 2>/dev/null || true
    log_pass "Intel thermald installed and enabled."
}

audit_persist() {
    log_info "Auditing systemd hardware tuning persistence..."
    if [[ -f "${PERSIST_SERVICE}" ]]; then
        log_pass "Persistence unit exists at ${PERSIST_SERVICE}"
    else
        log_info "Persistence unit not configured."
    fi
}

enable_persist() {
    log_info "Configuring hardware persistence service..."
    mkdir -p "${PERSIST_CONF_DIR}"
    if [[ ! -f "${PERSIST_CONF}" ]]; then
        cat <<EOF > "${PERSIST_CONF}"
CONSERVATION_MODE=1
PLATFORM_PROFILE=balanced
FN_LOCK=1
GPU_POWER_SAVE=auto
EOF
    fi

    cat <<EOF > "${PERSIST_SERVICE}"
[Unit]
Description=os-manager Lenovo Hardware Power & ACPI Tuning Persistence
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/osm tune hardware --apply
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload 2>/dev/null || true
    systemctl enable osm-hardware-tune.service 2>/dev/null || true
    log_pass "Hardware persistence service enabled at ${PERSIST_SERVICE}"
}

disable_persist() {
    log_info "Disabling hardware persistence service..."
    systemctl disable --now osm-hardware-tune.service 2>/dev/null || true
    rm -f "${PERSIST_SERVICE}"
    systemctl daemon-reload 2>/dev/null || true
    log_pass "Hardware persistence service disabled."
}

show_help() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --battery [status|on|off]         Inspect or set Lenovo battery conservation mode (60% threshold)
  --profile [status|quiet|balanced|performance]  Inspect or set Lenovo platform thermal profile
  --fn-lock [status|on|off]         Inspect or set Lenovo function key lock
  --gpu [status|power-save]         Inspect or configure discrete GPU Runtime D3 power gating
  --vaapi [status|install]          Inspect or install Intel VA-API video acceleration drivers
  --thermals [status|install]       Inspect or install Intel thermald daemon
  --persist [status|enable|disable] Inspect or configure boot persistence via systemd
  --audit                           Run full hardware power, thermal, and acceleration diagnostics
  -h, --help                        Display this help message
EOF
}

main() {
    local action="${1:-audit}"
    case "${action}" in
        --battery)
            local mode="${2:-status}"
            if [[ "${mode}" == "status" ]]; then
                echo "Lenovo Battery Conservation Mode: $(get_battery_status)"
            else
                set_battery_conservation "${mode}"
            fi
            ;;
        --profile)
            local prof="${2:-status}"
            if [[ "${prof}" == "status" ]]; then
                echo "Lenovo Platform Profile: $(get_platform_profile)"
            else
                set_platform_profile "${prof}"
            fi
            ;;
        --fn-lock)
            local fn_mode="${2:-status}"
            if [[ "${fn_mode}" == "status" ]]; then
                echo "Lenovo Fn-Lock: $(get_fn_lock_status)"
            else
                set_fn_lock "${fn_mode}"
            fi
            ;;
        --gpu)
            local gpu_sub="${2:-status}"
            if [[ "${gpu_sub}" == "power-save" ]]; then
                enforce_gpu_power_save
            else
                audit_gpu_power
            fi
            ;;
        --vaapi)
            local submode="${2:-status}"
            if [[ "${submode}" == "install" ]]; then
                install_vaapi_drivers
            else
                audit_vaapi
            fi
            ;;
        --thermals)
            local tmode="${2:-status}"
            if [[ "${tmode}" == "install" ]]; then
                install_thermals
            else
                audit_thermals
            fi
            ;;
        --persist)
            local pmode="${2:-status}"
            if [[ "${pmode}" == "enable" ]]; then
                enable_persist
            elif [[ "${pmode}" == "disable" ]]; then
                disable_persist
            else
                audit_persist
            fi
            ;;
        --audit)
            echo "=================================================="
            echo "       Hardware Tuning & Acceleration Audit       "
            echo "=================================================="
            log_info "Battery Conservation Mode: $(get_battery_status)"
            log_info "Platform Profile: $(get_platform_profile)"
            log_info "Fn-Lock: $(get_fn_lock_status)"
            audit_gpu_power || true
            audit_vaapi || true
            audit_thermals || true
            audit_persist || true
            ;;
        -h|--help)
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
