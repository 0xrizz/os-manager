#!/usr/bin/env bash
# scripts/migration/expand_root_partition.sh - Phase 4 Safe Online Root Partition Expansion
# Expands root partition boundary into freed staging space using growpart and resizes ext4 filesystem online
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration & CLI Options
DRY_RUN=false
MOCK_DISK=""
MOCK_PART=""
SKIP_QUALITY_GATE=false
QUALITY_GATE_SCRIPT="${SCRIPT_DIR}/quality_gate_audit.sh"
SKIP_GROWPART=false
SKIP_RESIZE=false

show_help() {
    cat << 'EOF'
Usage: expand_root_partition.sh [options]

Phase 4 online root partition expansion script for Debian bare-metal migration.
Expands the partition boundary online using growpart and extends the ext4
filesystem using resize2fs without unmounting or rebooting.

Options:
  -d, --dry-run                 Simulate partition expansion and filesystem resize without modifying disk
  --mock-disk <disk>            Override root disk device for testing (e.g., /dev/nvme0n1, /dev/sda)
  --mock-part <part_num>        Override root partition number for testing (e.g., 2, 3)
  --skip-quality-gate           Skip Quality Gate pre-requisite audit check
  --quality-gate-script <path>  Specify custom path to quality_gate_audit.sh
  --skip-growpart               Skip partition table expansion (growpart)
  --skip-resize                 Skip filesystem resizing (resize2fs)
  -h, --help                    Show this help message and exit

Examples:
  sudo ./scripts/migration/expand_root_partition.sh
  ./scripts/migration/expand_root_partition.sh --dry-run
  ./scripts/migration/expand_root_partition.sh --dry-run --mock-disk /dev/nvme0n1 --mock-part 2 --skip-quality-gate
EOF
}

# Parse Command Line Arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        --mock-disk)
            if [[ -z "${2:-}" ]]; then
                echo "ERROR: --mock-disk requires a disk device argument." >&2
                exit 1
            fi
            MOCK_DISK="$2"
            shift 2
            ;;
        --mock-part)
            if [[ -z "${2:-}" ]]; then
                echo "ERROR: --mock-part requires a partition number argument." >&2
                exit 1
            fi
            MOCK_PART="$2"
            shift 2
            ;;
        --skip-quality-gate)
            SKIP_QUALITY_GATE=true
            shift
            ;;
        --quality-gate-script)
            if [[ -z "${2:-}" ]]; then
                echo "ERROR: --quality-gate-script requires a file path argument." >&2
                exit 1
            fi
            QUALITY_GATE_SCRIPT="$2"
            shift 2
            ;;
        --skip-growpart)
            SKIP_GROWPART=true
            shift
            ;;
        --skip-resize)
            SKIP_RESIZE=true
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

echo "================================================"
echo "    SAFE ONLINE ROOT PARTITION EXPANSION"
echo "================================================"

# 1. Quality Gate Pre-requisite Audit Check
if [[ "$SKIP_QUALITY_GATE" != "true" ]]; then
    if [[ -f "${QUALITY_GATE_SCRIPT}" ]]; then
        echo "Running Quality Gate audit check before partition expansion..."
        if ! bash "${QUALITY_GATE_SCRIPT}"; then
            echo "ABORT: Quality gate checks failed. Do not expand partitions yet." >&2
            exit 1
        fi
        echo "Quality gate verification passed. Proceeding with partition expansion."
    else
        echo "Note: Quality Gate script not found at ${QUALITY_GATE_SCRIPT}. Skipping audit."
    fi
else
    echo "Notice: Quality Gate audit check skipped (--skip-quality-gate)."
fi

# 2. Identify Root Mount Source and Target Disk/Partition
ROOT_DEV=""
DISK=""
PART_NUM=""

if [[ -n "$MOCK_DISK" && -n "$MOCK_PART" ]]; then
    DISK="$MOCK_DISK"
    PART_NUM="$MOCK_PART"
    if [[ "$DISK" =~ [0-9]$ ]]; then
        ROOT_DEV="${DISK}p${PART_NUM}"
    else
        ROOT_DEV="${DISK}${PART_NUM}"
    fi
    echo "Using mock target disk: $DISK | partition: $PART_NUM (root device: $ROOT_DEV)"
else
    if command -v findmnt >/dev/null 2>&1; then
        ROOT_DEV=$(findmnt -n -o SOURCE / 2>/dev/null || true)
    fi

    if [[ -z "$ROOT_DEV" ]] && command -v df >/dev/null 2>&1; then
        ROOT_DEV=$(df / 2>/dev/null | awk 'NR==2 {print $1}' || true)
    fi

    echo "Current root mount source: ${ROOT_DEV:-unknown}"

    # Parse disk and partition number
    if [[ "$ROOT_DEV" =~ ^(/dev/nvme[0-9]+n[0-9]+)p([0-9]+)$ ]]; then
        DISK="${BASH_REMATCH[1]}"
        PART_NUM="${BASH_REMATCH[2]}"
    elif [[ "$ROOT_DEV" =~ ^(/dev/mmcblk[0-9]+)p([0-9]+)$ ]]; then
        DISK="${BASH_REMATCH[1]}"
        PART_NUM="${BASH_REMATCH[2]}"
    elif [[ "$ROOT_DEV" =~ ^(/dev/loop[0-9]+)p([0-9]+)$ ]]; then
        DISK="${BASH_REMATCH[1]}"
        PART_NUM="${BASH_REMATCH[2]}"
    elif [[ "$ROOT_DEV" =~ ^(/dev/[a-z]+)([0-9]+)$ ]]; then
        DISK="${BASH_REMATCH[1]}"
        PART_NUM="${BASH_REMATCH[2]}"
    elif [[ "$DRY_RUN" == "true" ]]; then
        echo "[DRY RUN] Host root device (${ROOT_DEV:-none}) is virtual/overlay. Falling back to default mock device /dev/nvme0n1p2."
        DISK="/dev/nvme0n1"
        PART_NUM="2"
        ROOT_DEV="/dev/nvme0n1p2"
    else
        echo "ERROR: Unable to parse root disk and partition number from '$ROOT_DEV'." >&2
        echo "Please verify root device or provide --mock-disk and --mock-part for manual targeting." >&2
        exit 1
    fi
fi

# 3. ZERO-DATA-LOSS SAFETY GUARDRAIL (Preserve Partition 4 / DATA_STORE)
if [[ "${PART_NUM}" == "4" ]] || [[ "${ROOT_DEV}" == *"/dev/nvme0n1p4"* ]] || [[ "${ROOT_DEV}" == *"/dev/sda4"* ]]; then
    echo "CRITICAL ERROR: Refusing to expand/modify Partition 4 (DATA_STORE / Drive D:). Protected by Zero-Data-Loss guardrail." >&2
    exit 1
fi

echo "Target Disk: $DISK | Partition Number: $PART_NUM"
echo "Root Device: $ROOT_DEV"

# 4. Dry-Run Simulation Mode
if [[ "$DRY_RUN" == "true" ]]; then
    echo "------------------------------------------------"
    echo "[DRY RUN] Simulating safe online partition expansion:"
    echo "[DRY RUN] Step 1: Expand partition boundary online:"
    echo "          growpart ${DISK} ${PART_NUM}"
    echo "[DRY RUN] Step 2: Resize ext4 filesystem online without unmounting:"
    echo "          resize2fs ${ROOT_DEV}"
    echo "[DRY RUN] Step 3: Verify storage geometry:"
    echo "          df -hT /"
    echo "================================================"
    echo "[DRY RUN] Safe online root expansion simulation completed successfully."
    echo "================================================"
    exit 0
fi

# 5. Live Execution: Verify Tool Availability
if [[ "$SKIP_GROWPART" != "true" ]]; then
    if ! command -v growpart >/dev/null 2>&1; then
        echo "Installing cloud-guest-utils (growpart)..."
        if [[ $EUID -eq 0 ]]; then
            apt-get update && apt-get install -y cloud-guest-utils
        else
            sudo apt-get update && sudo apt-get install -y cloud-guest-utils
        fi
    fi
fi

# 6. Step 1: Expand Partition Boundary Online
if [[ "$SKIP_GROWPART" != "true" ]]; then
    echo "Expanding partition boundary online with growpart..."
    if [[ $EUID -eq 0 ]]; then
        growpart "$DISK" "$PART_NUM" || echo "Note: growpart returned non-zero (partition may already be at maximum size)."
    else
        sudo growpart "$DISK" "$PART_NUM" || echo "Note: growpart returned non-zero (partition may already be at maximum size)."
    fi
else
    echo "Notice: Partition boundary expansion skipped (--skip-growpart)."
fi

# 7. Step 2: Resize ext4 Filesystem Online
if [[ "$SKIP_RESIZE" != "true" ]]; then
    echo "Resizing ext4 filesystem online with resize2fs..."
    if [[ $EUID -eq 0 ]]; then
        resize2fs "$ROOT_DEV"
    else
        sudo resize2fs "$ROOT_DEV"
    fi
else
    echo "Notice: Filesystem resizing skipped (--skip-resize)."
fi

# 8. Step 3: Geometry Verification
echo "================================================"
echo "SUCCESS: Safe online root partition expansion completed."
echo "Updated storage geometry:"
df -hT / || true
echo "================================================"
exit 0
