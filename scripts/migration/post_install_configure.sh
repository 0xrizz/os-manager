#!/usr/bin/env bash
# scripts/migration/post_install_configure.sh - Phase 4 Post-Installation Auto-Mount & Swapfile Setup
# Configures persistent /mnt/data mount for Partition 4 (DATA_STORE) and creates 8GB dynamic swapfile
set -euo pipefail

export PATH="$PATH:/usr/sbin:/sbin"

FSTAB_PATH="/etc/fstab"
MOUNT_POINT="/mnt/data"
PART_DEV="/dev/nvme0n1p4"
SWAP_PATH="/swapfile"
SWAP_SIZE="8G"
MOCK_UUID=""
DRY_RUN=false
SKIP_SWAP_OPS=false

show_help() {
    cat << 'EOF'
Usage: post_install_configure.sh [options]

Phase 4 post-installation configuration script for Debian bare-metal migration.
Configures persistent auto-mount for Partition 4 (DATA_STORE) at /mnt/data
and sets up an 8 GB dynamic swapfile.

Options:
  -d, --dry-run             Simulate configuration without making changes to the system
  -f, --fstab-target <path> Target fstab file path (default: /etc/fstab)
  -m, --mock-uuid <uuid>    Specify Partition 4 UUID manually (mock / testing)
  -p, --partition-dev <dev> Target block device for Partition 4 (default: /dev/nvme0n1p4)
  -s, --swap-size <size>    Swapfile allocation size (default: 8G)
  --swap-path <path>        Path to swapfile (default: /swapfile)
  --skip-swap-ops           Skip live fallocate/mkswap/swapon (for dry fstab testing)
  -h, --help                Show this help message and exit

Examples:
  sudo ./scripts/migration/post_install_configure.sh
  ./scripts/migration/post_install_configure.sh --dry-run
  ./scripts/migration/post_install_configure.sh --fstab-target /tmp/fstab --mock-uuid 1234-ABCD --skip-swap-ops
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -f|--fstab-target)
            if [[ -z "${2:-}" ]]; then
                echo "ERROR: --fstab-target requires a file path argument." >&2
                exit 1
            fi
            FSTAB_PATH="$2"
            shift 2
            ;;
        -m|--mock-uuid)
            if [[ -z "${2:-}" ]]; then
                echo "ERROR: --mock-uuid requires a UUID argument." >&2
                exit 1
            fi
            MOCK_UUID="$2"
            shift 2
            ;;
        -p|--partition-dev)
            if [[ -z "${2:-}" ]]; then
                echo "ERROR: --partition-dev requires a device path argument." >&2
                exit 1
            fi
            PART_DEV="$2"
            shift 2
            ;;
        -s|--swap-size)
            if [[ -z "${2:-}" ]]; then
                echo "ERROR: --swap-size requires a size argument (e.g., 8G)." >&2
                exit 1
            fi
            SWAP_SIZE="$2"
            shift 2
            ;;
        --swap-path)
            if [[ -z "${2:-}" ]]; then
                echo "ERROR: --swap-path requires a path argument." >&2
                exit 1
            fi
            SWAP_PATH="$2"
            shift 2
            ;;
        --skip-swap-ops)
            SKIP_SWAP_OPS=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option '$1'. Use --help for usage details." >&2
            exit 1
            ;;
    esac
done

echo "=================================================="
echo " Phase 4: Post-Installation Auto-Mount & Swapfile"
echo "=================================================="

# 1. Resolve Partition 4 UUID
DATA_UUID=""
if [[ -n "$MOCK_UUID" ]]; then
    DATA_UUID="$MOCK_UUID"
    echo "Using provided Partition UUID: ${DATA_UUID}"
else
    echo "Resolving UUID for Partition 4 (${PART_DEV})..."
    if command -v blkid >/dev/null 2>&1; then
        if [[ $EUID -eq 0 ]]; then
            DATA_UUID=$(blkid -s UUID -o value "${PART_DEV}" 2>/dev/null || true)
        else
            DATA_UUID=$(blkid -s UUID -o value "${PART_DEV}" 2>/dev/null || sudo blkid -s UUID -o value "${PART_DEV}" 2>/dev/null || true)
        fi
    fi
    if [[ -z "$DATA_UUID" ]] && command -v lsblk >/dev/null 2>&1; then
        DATA_UUID=$(lsblk -no UUID "${PART_DEV}" 2>/dev/null | tr -d ' \n\r' || true)
    fi
fi

if [[ -z "$DATA_UUID" ]]; then
    if [[ "$DRY_RUN" == "true" ]]; then
        DATA_UUID="MOCK-UUID-DRY-RUN-00000000"
        echo "[DRY RUN] Could not detect block device; fallback to simulated UUID: ${DATA_UUID}"
    else
        echo "ERROR: Unable to resolve UUID for ${PART_DEV}." >&2
        echo "Please verify partition number or use --mock-uuid <uuid>." >&2
        exit 1
    fi
fi

FSTAB_DATA_ENTRY="UUID=${DATA_UUID}  ${MOUNT_POINT}  ntfs-3g  defaults,uid=1000,gid=1000,umask=022,nofail  0  0"
FSTAB_SWAP_ENTRY="${SWAP_PATH} none swap sw 0 0"

# 2. Configure persistent /mnt/data mount
echo "--- 1. Configuring Mount Point & /etc/fstab for ${MOUNT_POINT} ---"
if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Would create mount directory: ${MOUNT_POINT}"
    echo "[DRY RUN] Target fstab file: ${FSTAB_PATH}"
    echo "[DRY RUN] Would check fstab and append if not present:"
    echo "          ${FSTAB_DATA_ENTRY}"
else
    # Create mount point directory
    if [[ ! -d "${MOUNT_POINT}" ]]; then
        echo "Creating mount directory: ${MOUNT_POINT}"
        if [[ $EUID -eq 0 ]]; then
            mkdir -p "${MOUNT_POINT}"
        else
            sudo mkdir -p "${MOUNT_POINT}"
        fi
    else
        echo "Mount directory ${MOUNT_POINT} already exists."
    fi

    # Append to fstab if not already present
    if [[ -f "${FSTAB_PATH}" ]] && grep -q "${DATA_UUID}" "${FSTAB_PATH}"; then
        echo "Partition UUID ${DATA_UUID} already configured in ${FSTAB_PATH}."
    else
        echo "Adding entry to ${FSTAB_PATH}:"
        echo "  ${FSTAB_DATA_ENTRY}"
        if [[ $EUID -eq 0 ]] || [[ ! -w "${FSTAB_PATH}" && ! -e "${FSTAB_PATH}" ]]; then
            echo "${FSTAB_DATA_ENTRY}" >> "${FSTAB_PATH}"
        elif [[ -w "${FSTAB_PATH}" ]]; then
            echo "${FSTAB_DATA_ENTRY}" >> "${FSTAB_PATH}"
        else
            echo "${FSTAB_DATA_ENTRY}" | sudo tee -a "${FSTAB_PATH}" >/dev/null
        fi
    fi

    # Live mount verification if configuring actual system fstab
    if [[ "${FSTAB_PATH}" == "/etc/fstab" ]]; then
        if findmnt -n "${MOUNT_POINT}" >/dev/null 2>&1; then
            echo "Mount directory ${MOUNT_POINT} is already mounted:"
            df -hT "${MOUNT_POINT}"
        else
            echo "Mounting all filesystems via 'mount -a'..."
            if [[ $EUID -eq 0 ]]; then
                mount -a || true
            else
                sudo mount -a || true
            fi

            if findmnt -n "${MOUNT_POINT}" >/dev/null 2>&1; then
                echo "Mount verification successful:"
                df -hT "${MOUNT_POINT}"
            else
                echo "NOTE: ${MOUNT_POINT} is not yet mounted (block device may not be attached in current environment)."
            fi
        fi
    fi
fi

# 3. Configure Dynamic Swapfile
echo "--- 2. Configuring ${SWAP_SIZE} Swapfile at ${SWAP_PATH} ---"
if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Would create ${SWAP_SIZE} swapfile at ${SWAP_PATH}"
    echo "[DRY RUN] Would set permissions 600 on ${SWAP_PATH}"
    echo "[DRY RUN] Would format swap with mkswap and activate with swapon"
    echo "[DRY RUN] Would append to fstab: ${FSTAB_SWAP_ENTRY}"
else
    # Create and activate swapfile if not skipping ops
    if [[ "$SKIP_SWAP_OPS" != "true" ]]; then
        if [[ ! -f "${SWAP_PATH}" ]]; then
            echo "Creating ${SWAP_SIZE} dynamic swapfile at ${SWAP_PATH}..."
            if [[ $EUID -eq 0 ]]; then
                fallocate -l "${SWAP_SIZE}" "${SWAP_PATH}" 2>/dev/null || dd if=/dev/zero of="${SWAP_PATH}" bs=1M count=8192 status=progress
                chmod 600 "${SWAP_PATH}"
                mkswap "${SWAP_PATH}"
                swapon "${SWAP_PATH}"
            else
                sudo fallocate -l "${SWAP_SIZE}" "${SWAP_PATH}" 2>/dev/null || sudo dd if=/dev/zero of="${SWAP_PATH}" bs=1M count=8192 status=progress
                sudo chmod 600 "${SWAP_PATH}"
                sudo mkswap "${SWAP_PATH}"
                sudo swapon "${SWAP_PATH}"
            fi
            echo "Swapfile created and activated successfully."
        else
            echo "Swapfile at ${SWAP_PATH} already exists."
            # Ensure swapon if not active
            if ! grep -q "${SWAP_PATH}" /proc/swaps 2>/dev/null; then
                echo "Activating existing swapfile..."
                if [[ $EUID -eq 0 ]]; then
                    swapon "${SWAP_PATH}" 2>/dev/null || true
                else
                    sudo swapon "${SWAP_PATH}" 2>/dev/null || true
                fi
            fi
        fi

        echo "Active swap devices (/proc/swaps):"
        cat /proc/swaps 2>/dev/null || true
    fi

    # Append swap entry to target fstab if not already present
    if [[ -f "${FSTAB_PATH}" ]] && grep -q "${SWAP_PATH}" "${FSTAB_PATH}"; then
        echo "Swapfile entry already exists in ${FSTAB_PATH}."
    else
        echo "Adding swap entry to ${FSTAB_PATH}:"
        echo "  ${FSTAB_SWAP_ENTRY}"
        if [[ $EUID -eq 0 ]] || [[ ! -w "${FSTAB_PATH}" && ! -e "${FSTAB_PATH}" ]]; then
            echo "${FSTAB_SWAP_ENTRY}" >> "${FSTAB_PATH}"
        elif [[ -w "${FSTAB_PATH}" ]]; then
            echo "${FSTAB_SWAP_ENTRY}" >> "${FSTAB_PATH}"
        else
            echo "${FSTAB_SWAP_ENTRY}" | sudo tee -a "${FSTAB_PATH}" >/dev/null
        fi
    fi
fi

echo "=================================================="
echo "SUCCESS: Post-installation configuration complete."
echo "=================================================="
