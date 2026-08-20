#!/usr/bin/env bash
# scripts/migration/verify_iso_squashfs.sh - Debian Live ISO Acquisition & Squashfs Size Verification
# Validates official Debian Live ISO integrity (SHA512) and ensures filesystem.squashfs fits within FAT32 single-file limits (< 4 GiB).
set -euo pipefail

TARGET_DIR="${TARGET_DIR:-/mnt/d/download}"
ISO_NAME="${ISO_NAME:-debian-live-12.8.0-amd64-gnome.iso}"
ISO_FILE="${1:-${TARGET_DIR}/${ISO_NAME}}"
ISO_URL="${ISO_URL:-https://cdimage.debian.org/cdimage/archive/12.8.0-live/amd64/iso-hybrid/${ISO_NAME}}"
FALLBACK_ISO_URL="${FALLBACK_ISO_URL:-https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/${ISO_NAME}}"
SHA512_URL="${SHA512_URL:-https://cdimage.debian.org/cdimage/archive/12.8.0-live/amd64/iso-hybrid/SHA512SUMS}"
FALLBACK_SHA512_URL="${FALLBACK_SHA512_URL:-https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/SHA512SUMS}"

mkdir -p "$TARGET_DIR"

if [[ ! -f "$ISO_FILE" ]] || (( $(stat -c %s "$ISO_FILE" 2>/dev/null || echo 0) < 1000000000 )); then
    echo "Debian Live GNOME ISO not fully downloaded at: ${ISO_FILE}"
    echo "Downloading official Debian Live GNOME ISO..."
    if ! curl -C - -L --progress-bar -f -o "$ISO_FILE" "$ISO_URL"; then
        echo "Primary download mirror failed, attempting fallback URL..."
        curl -C - -L --progress-bar -f -o "$ISO_FILE" "$FALLBACK_ISO_URL"
    fi
fi

SHA512_FILE="${TARGET_DIR}/SHA512SUMS"
if [[ ! -f "$SHA512_FILE" ]]; then
    echo "Downloading SHA512SUMS..."
    if ! curl -sL -f -o "$SHA512_FILE" "$SHA512_URL"; then
        curl -sL -f -o "$SHA512_FILE" "$FALLBACK_SHA512_URL"
    fi
fi

echo "Verifying SHA512 checksum for ${ISO_NAME}..."
if [[ -f "$SHA512_FILE" ]]; then
    (
        cd "$(dirname "$ISO_FILE")"
        base_name="$(basename "$ISO_FILE")"
        if grep -q "$base_name" "$SHA512_FILE"; then
            grep "$base_name" "$SHA512_FILE" | sha512sum -c --ignore-missing || {
                echo "ERROR: SHA512 checksum mismatch! File is corrupt or modified."
                exit 1
            }
            echo "PASS: SHA512 checksum verified successfully."
        else
            echo "WARNING: ${base_name} not found in SHA512SUMS, computing SHA512 directly..."
            sha512sum "$base_name"
        fi
    )
fi

echo "Inspecting squashfs filesystem size inside ISO..."
MOUNT_DIR=$(mktemp -d /tmp/iso_mount_XXXXXX)

cleanup() {
    if mountpoint -q "$MOUNT_DIR" 2>/dev/null; then
        sudo umount "$MOUNT_DIR" 2>/dev/null || true
    fi
    if [[ -d "$MOUNT_DIR" ]]; then
        rmdir "$MOUNT_DIR" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

sudo mount -o loop,ro "$ISO_FILE" "$MOUNT_DIR"

SQUASHFS_FILE="${MOUNT_DIR}/live/filesystem.squashfs"
if [[ ! -f "$SQUASHFS_FILE" ]]; then
    echo "ERROR: live/filesystem.squashfs not found inside mounted ISO!"
    exit 1
fi

SQUASHFS_SIZE=$(stat -c %s "$SQUASHFS_FILE")
MAX_FAT32_BYTES=4294967295 # 4 GiB - 1 byte (FAT32 single file size boundary)

echo "filesystem.squashfs size: ${SQUASHFS_SIZE} bytes ($(( SQUASHFS_SIZE / 1024 / 1024 )) MiB)"
echo "FAT32 single-file limit : ${MAX_FAT32_BYTES} bytes (4095 MiB)"

if (( SQUASHFS_SIZE > MAX_FAT32_BYTES )); then
    echo "ERROR: filesystem.squashfs exceeds FAT32 4GB limit! Staging requires exFAT/NTFS."
    exit 1
else
    echo "SUCCESS: filesystem.squashfs ($(( SQUASHFS_SIZE / 1024 / 1024 )) MiB) is safely within FAT32 single-file limits."
fi
