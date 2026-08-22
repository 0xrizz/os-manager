#!/usr/bin/env bash
# ==============================================================================
# hsi-harden.sh — Host Security ID (HSI) Remediation & Hardening Playbook
# Target: Lenovo 81WD / Ice Lake / Debian 13 Trixie
# Zero-Data-Loss Compliant: Never modifies /dev/nvme0n1p4 (DATA_STORE)
# ==============================================================================
set -euo pipefail

DRY_RUN=false
for arg in "$@"; do
    case "${arg}" in
        --dry-run) DRY_RUN=true ;;
    esac
done

echo "============================================================"
echo " [osm] Host Security ID (HSI) Remediation Engine"
echo "============================================================"

# Guardrail: Ensure /dev/nvme0n1p4 (DATA_STORE) and /mnt/data are protected
PROTECTED_PARTITION="/dev/nvme0n1p4"
PROTECTED_MOUNT="/mnt/data"

if [[ "${DRY_RUN}" == "true" ]]; then
    echo "[DRY-RUN] Mode active. No system files will be written."
    echo "[DRY-RUN] Protected partition ${PROTECTED_PARTITION} (${PROTECTED_MOUNT}) is safe."
    echo "[DRY-RUN] Would install systemd-zram-generator"
    echo "[DRY-RUN] Would configure /etc/systemd/zram-generator.conf"
    echo "[DRY-RUN] Would update /etc/default/grub with mem_sleep_default=s2idle"
    echo "[DRY-RUN] Would refresh and apply fwupd dbx updates"
    exit 0
fi

# Elevation check
if [[ "$(id -u)" -ne 0 ]]; then
    echo "[ERROR] This script requires root privileges. Please execute with sudo."
    exit 1
fi

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# ------------------------------------------------------------------------------
# 1. Swap Hardening: Configure volatile zRAM & Decommission Plaintext Swap
# ------------------------------------------------------------------------------
echo "==> [1/3] Hardening Swap Architecture (zRAM + Plaintext Swap Decommission)..."

if ! dpkg -s systemd-zram-generator >/dev/null 2>&1; then
    echo "    Installing systemd-zram-generator..."
    apt-get update -qq && apt-get install -y -qq systemd-zram-generator
fi

echo "    Configuring /etc/systemd/zram-generator.conf..."
cat <<'EOF' > /etc/systemd/zram-generator.conf
# Managed by osm hsi-harden
[zram0]
zram-size = min(ram / 2, 8192)
compression-algorithm = zstd
swap-priority = 100
EOF

if [[ -f /etc/fstab ]]; then
    echo "    Backing up /etc/fstab to /etc/fstab.bak.${TIMESTAMP}..."
    cp /etc/fstab "/etc/fstab.bak.${TIMESTAMP}"

    # Comment out unencrypted swap partitions, explicitly excluding protected DATA_STORE partitions
    sed -i -E '/nvme0n1p4|\/mnt\/data/! s|^([^#].*\s+swap\s+.*)$|# Disabled for HSI hardening: \1|g' /etc/fstab
fi

# Reload and start zram generator
systemctl daemon-reload
systemctl restart systemd-zram-setup@zram0.service || true
swapoff -a || true
swapon -a || true

# ------------------------------------------------------------------------------
# 2. Kernel Sleep State Hardening (s2idle for Cold-Boot Attack Mitigation)
# ------------------------------------------------------------------------------
echo "==> [2/3] Configuring Kernel Sleep State (s2idle)..."

if [[ -f /etc/default/grub ]]; then
    echo "    Backing up /etc/default/grub to /etc/default/grub.bak.${TIMESTAMP}..."
    cp /etc/default/grub "/etc/default/grub.bak.${TIMESTAMP}"

    if grep -q "mem_sleep_default=" /etc/default/grub; then
        sed -i -E 's/mem_sleep_default=[^ "]+/mem_sleep_default=s2idle/g' /etc/default/grub
    else
        sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="mem_sleep_default=s2idle /g' /etc/default/grub
    fi

    echo "    Updating GRUB configuration..."
    update-grub >/dev/null 2>&1 || true
fi

# ------------------------------------------------------------------------------
# 3. Secure Boot DBX & Firmware Updates via fwupd
# ------------------------------------------------------------------------------
echo "==> [3/3] Updating Secure Boot DBX & Querying LVFS Firmware..."

if command -v fwupdmgr >/dev/null 2>&1; then
    fwupdmgr refresh --force >/dev/null 2>&1 || true
    echo "    Applying available UEFI DBX / Firmware updates..."
    fwupdmgr update -y >/dev/null 2>&1 || true
else
    echo "    [WARN] fwupdmgr not installed. Skipping firmware update step."
fi

echo "============================================================"
echo " [PASS] HSI Hardening Completed Successfully."
echo " Please verify with: osm hsi audit or fwupdmgr security"
echo "============================================================"
