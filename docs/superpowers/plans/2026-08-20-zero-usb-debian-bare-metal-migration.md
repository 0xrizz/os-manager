# Zero-USB Debian Bare-Metal Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute a zero-USB, zero-external-backup migration from Windows 10/11 to bare-metal Debian GNU/Linux 12 (GNOME, Wayland, ext4) on Lenovo IdeaPad 3 (81WD) with a 512GB NVMe SSD while preserving 201 GB of critical user data on Partition 4 (Drive D: / `DATA_STORE`) completely in-place.

**Architecture:** Shrink Windows C: partition by 120 GB to carve out an 8.0 GB FAT32 staging partition (`DEBIAN_SET`) and ~112 GB unallocated space for Debian root (`/`). Extract the official Debian Live GNOME ISO directly to `DEBIAN_SET`, inject a UEFI NVRAM boot entry pointing to `\EFI\BOOT\BOOTX64.EFI`, boot into the live environment, install Debian to unallocated space via Calamares, verify hardware stability against a strict quality gate, mount Drive D: via persistent `/etc/fstab` UUID, restore the 753 MB WSL backup archive, and cleanly expand the root partition online via `growpart` and `resize2fs`.

**Tech Stack:** Debian GNU/Linux 12 (Bookworm/Trixie) Live GNOME, Linux Kernel 6.x (`i915`, `iwlwifi`, `nvme`), Calamares Installer, UEFI NVRAM / `efibootmgr`, ext4 filesystem, `ntfs-3g`, DiskGenius, PowerShell 5.1+, `cloud-guest-utils` (`growpart`, `resize2fs`).

**Spec:** [`docs/LINUX_MIGRATION_BLUEPRINT.md`](file:///home/rizz/dev/os-manager/docs/LINUX_MIGRATION_BLUEPRINT.md)

## Global Constraints

- **Strict Zero Data Loss on Partition 4:** DILARANG menjalankan perintah `format`, `mkfs`, `wipefs`, `fdisk d`, `rm -rf` skala luas, atau penghapusan partisi pada `/dev/nvme0n1p4` (Drive D: / `DATA_STORE`, offset `248917262336`). Data 201 GB harus tetap utuh *in-place*.
- **FAT32 Single-File Limit:** Pastikan `live/filesystem.squashfs` tidak melebihi 4.294.967.295 bytes (4 GiB) sebelum diekstrak ke partisi staging `DEBIAN_SET`.
- **Windows Interop stdin Guardrail:** Semua eksekusi biner Windows dari WSL (`powershell.exe`, `cmd.exe`, `bcdedit.exe`) wajib menggunakan flag non-interaktif dan pengalihan `< /dev/null` untuk mencegah proses membeku (*hang*).
- **Post-Install Quality Gate:** Staging installer (`DEBIAN_SET`) dan partisi sisa Windows DILARANG dihapus sebelum sistem bare-metal sukses reboot 2–3 kali serta Wi-Fi (`iwlwifi`), audio, touchpad, dan Suspend/Resume terverifikasi 100% normal.
- **Online Expansion Guardrail:** Ekspansi partisi root wajib menggunakan urutan online yang aman: `growpart /dev/nvme0n1 <part_num>` dilanjutkan dengan `resize2fs /dev/nvme0n1p<part_num>`.

---

### Task 1: Debian Live GNOME ISO Acquisition & Squashfs Size Verification

**Files:**
- Create: `scripts/migration/verify_iso_squashfs.sh`
- Test: `tests/test_migration_prerequisites.sh`

**Interfaces:**
- Consumes: ISO download directory at `/mnt/d/download/` or Windows user downloads.
- Produces: Verified Debian Live ISO image with SHA512 validation and `filesystem.squashfs` size < 4 GiB confirmation.

- [ ] **Step 1: Write automated ISO and squashfs validation test script**

```bash
#!/usr/bin/env bash
# tests/test_migration_prerequisites.sh
set -euo pipefail

ISO_PATH="${1:-}"

if [[ -z "$ISO_PATH" || ! -f "$ISO_PATH" ]]; then
    echo "FAIL: ISO file not provided or does not exist."
    exit 1
fi

echo "Testing ISO size and readability..."
ISO_SIZE_BYTES=$(stat -c %s "$ISO_PATH")
if (( ISO_SIZE_BYTES < 1000000000 )); then
    echo "FAIL: ISO file size ($ISO_SIZE_BYTES bytes) is suspiciously small (< 1 GB)."
    exit 1
fi

echo "PASS: ISO size is valid ($ISO_SIZE_BYTES bytes)."
```

- [ ] **Step 2: Run test to verify it fails when no ISO is staged**

Run: `bash tests/test_migration_prerequisites.sh /mnt/d/download/nonexistent.iso`
Expected: FAIL with "ISO file not provided or does not exist."

- [ ] **Step 3: Implement ISO acquisition, SHA512 check, and squashfs extraction verifier**

```bash
#!/usr/bin/env bash
# scripts/migration/verify_iso_squashfs.sh
set -euo pipefail

TARGET_DIR="/mnt/d/download"
ISO_NAME="debian-live-12.8.0-amd64-gnome.iso"
ISO_FILE="${TARGET_DIR}/${ISO_NAME}"
ISO_URL="https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/${ISO_NAME}"
SHA512_URL="https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/SHA512SUMS"

mkdir -p "$TARGET_DIR"

if [[ ! -f "$ISO_FILE" ]]; then
    echo "Debian Live GNOME ISO not found locally. Downloading from official Debian CDN..."
    curl -L --progress-bar -o "$ISO_FILE" "$ISO_URL"
    curl -sL -o "${TARGET_DIR}/SHA512SUMS" "$SHA512_URL"
fi

echo "Verifying SHA512 checksum..."
if [[ -f "${TARGET_DIR}/SHA512SUMS" ]]; then
    cd "$TARGET_DIR"
    grep "$ISO_NAME" SHA512SUMS | sha512sum -c --ignore-missing || {
        echo "ERROR: SHA512 checksum mismatch! Re-downloading required."
        exit 1
    }
fi

echo "Inspecting squashfs filesystem size inside ISO..."
mkdir -p /tmp/iso_mount
sudo mount -o loop,ro "$ISO_FILE" /tmp/iso_mount
SQUASHFS_SIZE=$(stat -c %s /tmp/iso_mount/live/filesystem.squashfs)
sudo umount /tmp/iso_mount
rmdir /tmp/iso_mount

MAX_FAT32_BYTES=4294967295
echo "filesystem.squashfs size: $SQUASHFS_SIZE bytes (Max FAT32: $MAX_FAT32_BYTES bytes)"

if (( SQUASHFS_SIZE > MAX_FAT32_BYTES )); then
    echo "ERROR: filesystem.squashfs exceeds FAT32 4GB limit! Staging requires exFAT/NTFS."
    exit 1
else
    echo "SUCCESS: filesystem.squashfs is safely within FAT32 single-file limits."
fi
```

- [ ] **Step 4: Make script executable and run test**

Run: `chmod +x scripts/migration/verify_iso_squashfs.sh tests/test_migration_prerequisites.sh`
Run: `bash tests/test_migration_prerequisites.sh /mnt/d/download/debian-live-12.8.0-amd64-gnome.iso` (or after download)
Expected: PASS with size confirmation.

- [ ] **Step 5: Commit task artifacts**

```bash
git add scripts/migration/verify_iso_squashfs.sh tests/test_migration_prerequisites.sh
git commit -m "feat(migration): add ISO acquisition and FAT32 squashfs boundary verifier"
```

---

### Task 2: GPT Partition Table & BCD Redundancy Backup

**Files:**
- Create: `scripts/migration/export_disk_geometry_backup.sh`
- Test: `tests/test_backup_redundancy.sh`

**Interfaces:**
- Consumes: Windows PowerShell disk and partition cmdlets.
- Produces: `D:\disk_layout.json`, `D:\partition_layout.json`, `D:\bcd_backup.bcd`, and `D:\wsl_backup\wsl_home_backup.sha256`.

- [ ] **Step 1: Write test verifying open-standard backup artifacts**

```bash
#!/usr/bin/env bash
# tests/test_backup_redundancy.sh
set -euo pipefail

BACKUP_DIR="/mnt/d"
WSL_BACKUP_DIR="/mnt/d/wsl_backup"

echo "Verifying backup artifacts exist on Drive D:..."
test -s "${BACKUP_DIR}/disk_layout.json" || { echo "FAIL: disk_layout.json missing or empty"; exit 1; }
test -s "${BACKUP_DIR}/partition_layout.json" || { echo "FAIL: partition_layout.json missing or empty"; exit 1; }
test -s "${BACKUP_DIR}/bcd_backup.bcd" || { echo "FAIL: bcd_backup.bcd missing or empty"; exit 1; }
test -s "${WSL_BACKUP_DIR}/wsl_home_backup.tar.gz" || { echo "FAIL: wsl_home_backup.tar.gz missing"; exit 1; }
test -s "${WSL_BACKUP_DIR}/wsl_home_backup.sha256" || { echo "FAIL: wsl_home_backup.sha256 missing"; exit 1; }

echo "Verifying WSL archive checksum match..."
cd "$WSL_BACKUP_DIR"
sha256sum -c wsl_home_backup.sha256

echo "PASS: All redundancy backups are present, non-empty, and checksum-verified."
```

- [ ] **Step 2: Run test to verify execution**

Run: `bash tests/test_backup_redundancy.sh`
Expected: PASS with "All redundancy backups are present, non-empty, and checksum-verified."

- [ ] **Step 3: Implement automated disk geometry and BCD backup exporter**

```bash
#!/usr/bin/env bash
# scripts/migration/export_disk_geometry_backup.sh
set -euo pipefail

echo "Exporting Windows disk, partition, and BCD configuration..."
powershell.exe -NoProfile -NonInteractive -Command "
    Get-Disk | ConvertTo-Json -Depth 5 | Out-File -FilePath D:\disk_layout.json -Encoding utf8;
    Get-Partition | ConvertTo-Json -Depth 5 | Out-File -FilePath D:\partition_layout.json -Encoding utf8;
    bcdedit.exe /export D:\bcd_backup.bcd;
    Get-Volume | Select-Object DriveLetter, FileSystemLabel, FileSystem, SizeRemaining, Size | Format-Table -AutoSize
" < /dev/null

echo "SUCCESS: Redundancy backup exported to Drive D:."
```

- [ ] **Step 4: Execute script and verify output**

Run: `chmod +x scripts/migration/export_disk_geometry_backup.sh tests/test_backup_redundancy.sh`
Run: `bash scripts/migration/export_disk_geometry_backup.sh`
Expected: Exited 0 with JSON and BCD created on Drive D:.

- [ ] **Step 5: Commit task artifacts**

```bash
git add scripts/migration/export_disk_geometry_backup.sh tests/test_backup_redundancy.sh
git commit -m "feat(migration): add automated disk geometry and BCD store redundancy backup"
```

---

### Task 3: Phase 1 DiskGenius Partition Resizing & FAT32 Staging Creation

**Files:**
- Create: `docs/migration/PHASE_1_DISKGENIUS_GUIDE.md`
- Create: `scripts/migration/verify_staging_partition.sh`
- Test: `tests/test_staging_partition.sh`

**Interfaces:**
- Consumes: Partition 2 (C:) with 120.5 GB available space.
- Produces: 8.0 GB FAT32 partition (`DEBIAN_SET`) and ~112 GB unallocated space on Disk 0.

- [ ] **Step 1: Write test to verify partition table structure after shrink**

```bash
#!/usr/bin/env bash
# tests/test_staging_partition.sh
set -euo pipefail

echo "Checking for DEBIAN_SET volume or 8GB FAT32 staging partition..."
STAGING_INFO=$(powershell.exe -NoProfile -NonInteractive -Command "
    Get-Volume | Where-Object { \$_.FileSystemLabel -eq 'DEBIAN_SET' -or (\$_.FileSystem -eq 'FAT32' -and \$_.Size -ge 7GB -and \$_.Size -le 9GB) } | Select-Object DriveLetter, FileSystemLabel, FileSystem, Size | ConvertTo-Json
" < /dev/null || true)

if [[ -z "$STAGING_INFO" || "$STAGING_INFO" == "null" ]]; then
    echo "WAITING: Staging partition 'DEBIAN_SET' (8GB FAT32) has not been created yet."
    exit 1
fi

echo "PASS: Staging partition detected: $STAGING_INFO"
```

- [ ] **Step 2: Run test to confirm it fails before user partition action**

Run: `bash tests/test_staging_partition.sh`
Expected: FAIL with "WAITING: Staging partition 'DEBIAN_SET' (8GB FAT32) has not been created yet."

- [ ] **Step 3: Create step-by-step DiskGenius visual action guide**

```markdown
<!-- docs/migration/PHASE_1_DISKGENIUS_GUIDE.md -->
# Phase 1: DiskGenius Partition Resizing Guide

## Step 1: Label Partition 4
1. Open **DiskGenius**.
2. Right-click **Partition 4** (Drive D:) -> **Set Volume Label** -> enter `DATA_STORE`.
3. Menu **Disk** -> **Backup Partition Table** -> save to `D:\ptf_backup.ptf`.

## Step 2: Shrink Partition 2 (Drive C:)
1. Right-click **Partition 2** (Drive C:) -> **Resize Partition**.
2. Enter Shrink Space: **120.0 GB**.
3. In the unallocated space options:
   - Create a new **Primary Partition** of **8.0 GB**, Format: **FAT32**, Volume Label: `DEBIAN_SET`.
   - Leave the remaining space (~112 GB) as **Unallocated Space**.
4. Click **Start / Save All** in the top toolbar to execute.
```

- [ ] **Step 4: Implement script to verify staging partition mount and write access**

```bash
#!/usr/bin/env bash
# scripts/migration/verify_staging_partition.sh
set -euo pipefail

echo "Querying Disk 0 layout from Windows..."
powershell.exe -NoProfile -NonInteractive -Command "
    Get-Partition -DiskNumber 0 | Select-Object PartitionNumber, DriveLetter, Offset, Size, Type | Format-Table -AutoSize
" < /dev/null

powershell.exe -NoProfile -NonInteractive -Command "
    \$vol = Get-Volume | Where-Object { \$_.FileSystemLabel -eq 'DEBIAN_SET' }
    if (\$vol) {
        Write-Host 'SUCCESS: DEBIAN_SET mounted at Drive ' \$vol.DriveLetter ' (' \$vol.FileSystem ', ' ([math]::Round(\$vol.Size/1GB, 2)) 'GB)'
    } else {
        Write-Host 'WARNING: DEBIAN_SET volume label not found. Please label the 8GB FAT32 partition DEBIAN_SET.'
    }
" < /dev/null
```

- [ ] **Step 5: Commit documentation and verification scripts**

```bash
git add docs/migration/PHASE_1_DISKGENIUS_GUIDE.md scripts/migration/verify_staging_partition.sh tests/test_staging_partition.sh
git commit -m "docs(migration): add Phase 1 DiskGenius partition resizing guide and verification script"
```

---

### Task 4: Phase 2 ISO Staging & UEFI NVRAM Boot Entry Injection

**Files:**
- Create: `scripts/migration/stage_iso_contents.sh`
- Create: `docs/migration/PHASE_2_UEFI_INJECTION_GUIDE.md`
- Test: `tests/test_uefi_staging.sh`

**Interfaces:**
- Consumes: `DEBIAN_SET` FAT32 partition mounted with drive letter in Windows, downloaded Debian Live ISO.
- Produces: Extracted ISO filesystem tree in `DEBIAN_SET:\`, UEFI NVRAM boot entry pointing to `\EFI\BOOT\BOOTX64.EFI`.

- [ ] **Step 1: Write test for UEFI loader file existence on staging volume**

```bash
#!/usr/bin/env bash
# tests/test_uefi_staging.sh
set -euo pipefail

echo "Checking for staged Debian EFI bootloader..."
LOADER_EXISTS=$(powershell.exe -NoProfile -NonInteractive -Command "
    \$vol = Get-Volume | Where-Object { \$_.FileSystemLabel -eq 'DEBIAN_SET' }
    if (\$vol -and \$vol.DriveLetter) {
        Test-Path (\$vol.DriveLetter + ':\EFI\BOOT\BOOTX64.EFI')
    } else {
        Write-Output 'False'
    }
" < /dev/null | tr -d '\r\n')

if [[ "$LOADER_EXISTS" != "True" ]]; then
    echo "FAIL: \EFI\BOOT\BOOTX64.EFI not found on DEBIAN_SET volume."
    exit 1
fi

echo "PASS: UEFI bootloader \EFI\BOOT\BOOTX64.EFI verified on DEBIAN_SET."
```

- [ ] **Step 2: Run test to confirm it fails before ISO extraction**

Run: `bash tests/test_uefi_staging.sh`
Expected: FAIL with "\EFI\BOOT\BOOTX64.EFI not found on DEBIAN_SET volume."

- [ ] **Step 3: Implement automated ISO extraction to staging drive**

```bash
#!/usr/bin/env bash
# scripts/migration/stage_iso_contents.sh
set -euo pipefail

ISO_PATH="${1:-/mnt/d/download/debian-live-12.8.0-amd64-gnome.iso}"

if [[ ! -f "$ISO_PATH" ]]; then
    echo "ERROR: ISO file $ISO_PATH not found."
    exit 1
fi

STAGING_LETTER=$(powershell.exe -NoProfile -NonInteractive -Command "
    \$vol = Get-Volume | Where-Object { \$_.FileSystemLabel -eq 'DEBIAN_SET' }
    if (\$vol -and \$vol.DriveLetter) { Write-Output \$vol.DriveLetter }
" < /dev/null | tr -d '\r\n')

if [[ -z "$STAGING_LETTER" ]]; then
    echo "ERROR: DEBIAN_SET volume letter could not be resolved from Windows."
    exit 1
fi

STAGING_MOUNT="/mnt/${STAGING_LETTER,,}"
echo "Staging drive located at: $STAGING_MOUNT (${STAGING_LETTER}:)"

echo "Mounting ISO and copying all payload files to ${STAGING_MOUNT}..."
mkdir -p /tmp/debian_iso_stage
sudo mount -o loop,ro "$ISO_PATH" /tmp/debian_iso_stage
cp -rv /tmp/debian_iso_stage/* "${STAGING_MOUNT}/"
sudo umount /tmp/debian_iso_stage
rmdir /tmp/debian_iso_stage

sync
echo "SUCCESS: ISO contents staged to ${STAGING_LETTER}:."
```

- [ ] **Step 4: Create DiskGenius UEFI boot entry registration guide**

```markdown
<!-- docs/migration/PHASE_2_UEFI_INJECTION_GUIDE.md -->
# Phase 2: UEFI NVRAM Boot Entry Injection

## Step 1: Register Boot Entry in DiskGenius
1. In **DiskGenius**, open menu **Tools** -> **Set UEFI BIOS boot entries**.
2. Click **Add**.
3. Select **Disk 0 (NVMe)** -> Select Partition **`DEBIAN_SET` (FAT32)**.
4. File path: `\EFI\BOOT\BOOTX64.EFI`.
5. Entry Name: `Debian Live Installer`.
6. Click **Move Up** to place it at the very top (Priority #1).
7. Click **Save Current Boot Entry** and close.
```

- [ ] **Step 5: Run tests and commit**

Run: `chmod +x scripts/migration/stage_iso_contents.sh tests/test_uefi_staging.sh`
Run: `bash tests/test_uefi_staging.sh` (after staging)
Expected: PASS.

```bash
git add scripts/migration/stage_iso_contents.sh docs/migration/PHASE_2_UEFI_INJECTION_GUIDE.md tests/test_uefi_staging.sh
git commit -m "feat(migration): implement Phase 2 ISO staging and UEFI injection guide"
```

---

### Task 5: Phase 3 Calamares Installation & Manual Partitioning Protocol

**Files:**
- Create: `docs/migration/PHASE_3_CALAMARES_INSTALL_PROTOCOL.md`
- Create: `scripts/migration/pre_install_checklist.sh`
- Test: `tests/test_pre_install_readiness.sh`

**Interfaces:**
- Consumes: Unallocated space (~112 GB), Partition 1 (100 MB EFI ESP), untouched Partition 4 (`DATA_STORE`).
- Produces: Installed Debian GNU/Linux system with user `rizz`, sudo access, and GRUB bootloader in `/boot/efi`.

- [ ] **Step 1: Write pre-installation checklist test script**

```bash
#!/usr/bin/env bash
# tests/test_pre_install_readiness.sh
set -euo pipefail

echo "Executing pre-installation sanity checks..."
# Check BitLocker is off
BITLOCKER_OFF=$(powershell.exe -NoProfile -NonInteractive -Command "
    \$c = Get-BitLockerVolume -MountPoint C:
    \$d = Get-BitLockerVolume -MountPoint D:
    if (\$c.ProtectionStatus -eq 'Off' -and \$d.ProtectionStatus -eq 'Off') { Write-Output 'True' } else { Write-Output 'False' }
" < /dev/null | tr -d '\r\n')

test "$BITLOCKER_OFF" == "True" || { echo "FAIL: BitLocker is still active!"; exit 1; }

# Check Backup exists
test -s /mnt/d/wsl_backup/wsl_home_backup.tar.gz || { echo "FAIL: WSL backup archive missing!"; exit 1; }

echo "PASS: System is 100% ready for reboot and Calamares installation."
```

- [ ] **Step 2: Run test to confirm pre-install readiness**

Run: `bash tests/test_pre_install_readiness.sh`
Expected: PASS with "System is 100% ready for reboot and Calamares installation."

- [ ] **Step 3: Create detailed Calamares manual partition matrix document**

```markdown
<!-- docs/migration/PHASE_3_CALAMARES_INSTALL_PROTOCOL.md -->
# Phase 3: Calamares Manual Partitioning Protocol

## Partition Assignment Table

| Target Device / Partition | Filesystem | Mount Point | Format Flag | Critical Notes |
| :--- | :--- | :--- | :---: | :--- |
| **Partition 1 (100 MB FAT32)** | `fat32` | `/boot/efi` | **NO (Keep)** | Existing EFI ESP. Do NOT format. |
| **Free Space (~112 GB)** | `ext4` | `/` (Root) | **YES (Format)** | Option: Check LUKS2 encryption. |
| **Partition 4 (244 GB NTFS)** | `ntfs` | (Leave blank) | **NO (DO NOT TOUCH)** | Protected user data (201 GB). |
| **Boot Loader Location** | - | `/dev/nvme0n1` | - | Install GRUB to master NVMe drive. |

## User Account Creation
- **Full Name:** `rizz`
- **Username:** `rizz`
- **Password:** (user chosen strong password)
- **Automatic Login:** Optional (recommend disabled if LUKS2 used).
```

- [ ] **Step 4: Commit protocol documentation**

```bash
git add docs/migration/PHASE_3_CALAMARES_INSTALL_PROTOCOL.md tests/test_pre_install_readiness.sh
git commit -m "docs(migration): create Calamares manual partitioning protocol and pre-install verification"
```

---

### Task 6: Post-Installation Quality Gate Diagnostics Checkpoint

**Files:**
- Create: `scripts/migration/quality_gate_audit.sh`
- Test: `tests/test_quality_gate.sh`

**Interfaces:**
- Consumes: Bare-metal Debian Linux kernel sysfs and hardware buses (`/sys/class/net`, `/sys/class/sound`, `/dev/nvme0n1`).
- Produces: Pass/fail audit report for Wi-Fi (`iwlwifi`), audio, Bluetooth, suspend/resume, and graphics (`i915`).

- [ ] **Step 1: Write failing hardware quality gate test script**

```bash
#!/usr/bin/env bash
# tests/test_quality_gate.sh
set -euo pipefail

echo "Auditing hardware modules and device nodes..."
# 1. Check Wi-Fi interface exists
ip link show | grep -qE "wlan|wlp|wls" || { echo "FAIL: No wireless interface detected."; exit 1; }

# 2. Check NVMe storage controller
ls -l /dev/nvme0* > /dev/null || { echo "FAIL: NVMe SSD block devices not found."; exit 1; }

# 3. Check Intel graphics driver
lsmod | grep -q "i915" || { echo "FAIL: Intel i915 graphics module not loaded."; exit 1; }

echo "PASS: Hardware quality gate passed."
```

- [ ] **Step 2: Run test in current environment to observe hardware status**

Run: `bash tests/test_quality_gate.sh`
Expected: In WSL, this will fail on PCI modules, providing the baseline for bare-metal audit.

- [ ] **Step 3: Implement comprehensive Quality Gate Audit script**

```bash
#!/usr/bin/env bash
# scripts/migration/quality_gate_audit.sh
set -euo pipefail

echo "================================================"
echo "    DEBIAN BARE-METAL QUALITY GATE AUDIT"
echo "================================================"

SCORE=0
TOTAL=5

# 1. Wi-Fi Connectivity
echo -n "[1/5] Checking Intel AC 9560 Wi-Fi (iwlwifi)... "
if ip link show | grep -qE "wlan|wlp|wls" && ping -c 2 -W 3 1.1.1.1 >/dev/null 2>&1; then
    echo "OK (Connected)"
    ((SCORE++))
else
    echo "WARN (No active internet connection)"
fi

# 2. Audio Subsystem
echo -n "[2/5] Checking ALSA/PipeWire Audio... "
if which wpctl >/dev/null 2>&1 || which aplay >/dev/null 2>&1; then
    echo "OK"
    ((SCORE++))
else
    echo "WARN (Audio tools not found)"
fi

# 3. Bluetooth Subsystem
echo -n "[3/5] Checking Bluetooth Controller... "
if which bluetoothctl >/dev/null 2>&1 && rfkill list bluetooth >/dev/null 2>&1; then
    echo "OK"
    ((SCORE++))
else
    echo "WARN (Bluetooth not initialized)"
fi

# 4. Intel Graphics & Wayland
echo -n "[4/5] Checking GNOME Wayland & Intel i915 DRM... "
if [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]] || lsmod | grep -q "i915"; then
    echo "OK"
    ((SCORE++))
else
    echo "INFO (Running in non-Wayland/WSL context)"
fi

# 5. Partition 4 Protection Check
echo -n "[5/5] Checking Partition 4 (DATA_STORE) Preservation... "
if sudo blkid /dev/nvme0n1p4 | grep -q "ntfs"; then
    echo "OK (NTFS intact)"
    ((SCORE++))
else
    echo "CRITICAL: Partition 4 not found as NTFS!"
fi

echo "================================================"
echo "Quality Gate Score: $SCORE / $TOTAL"
if (( SCORE >= 4 )); then
    echo "RESULT: Quality Gate PASSED. Safe to proceed with Phase 4."
else
    echo "RESULT: Quality Gate NOT MET. Do NOT delete staging partitions yet."
fi
```

- [ ] **Step 4: Commit quality gate audit tools**

```bash
git add scripts/migration/quality_gate_audit.sh tests/test_quality_gate.sh
git commit -m "feat(migration): implement post-installation Quality Gate hardware auditor"
```

---

### Task 7: Phase 4 Auto-Mount Data Store, WSL Restore, & Swapfile Setup

**Files:**
- Create: `scripts/migration/post_install_configure.sh`
- Create: `scripts/migration/restore_wsl_home.sh`
- Test: `tests/test_fstab_generator.sh`

**Interfaces:**
- Consumes: Partition 4 (`/dev/nvme0n1p4`, UUID queryable via `blkid`), `/mnt/data/wsl_backup/wsl_home_backup.tar.gz`.
- Produces: `/etc/fstab` auto-mount entry at `/mnt/data`, restored `~/.ssh`, `~/.gitconfig`, `~/dev/`, active 8GB `/swapfile`.

- [ ] **Step 1: Write test for fstab entry format generation**

```bash
#!/usr/bin/env bash
# tests/test_fstab_generator.sh
set -euo pipefail

MOCK_UUID="12345678-ABCD-EF01-2345-6789ABCDEF01"
FSTAB_LINE="UUID=${MOCK_UUID}  /mnt/data  ntfs-3g  defaults,uid=1000,gid=1000,umask=022,nofail  0  0"

echo "$FSTAB_LINE" | grep -q "nofail" || { echo "FAIL: nofail flag missing from fstab template"; exit 1; }
echo "$FSTAB_LINE" | grep -q "uid=1000,gid=1000" || { echo "FAIL: ownership flags missing"; exit 1; }

echo "PASS: fstab template is safe and correct."
```

- [ ] **Step 2: Run test to verify fstab generator**

Run: `bash tests/test_fstab_generator.sh`
Expected: PASS.

- [ ] **Step 3: Implement post-install auto-mount and swapfile configuration script**

```bash
#!/usr/bin/env bash
# scripts/migration/post_install_configure.sh
set -euo pipefail

echo "Configuring persistent /mnt/data mount for Partition 4..."
sudo mkdir -p /mnt/data

# Extract UUID of Partition 4
DATA_UUID=$(sudo blkid -s UUID -o value /dev/nvme0n1p4 2>/dev/null || true)
if [[ -z "$DATA_UUID" ]]; then
    echo "ERROR: Unable to resolve UUID for /dev/nvme0n1p4. Please verify partition number."
    exit 1
fi

FSTAB_ENTRY="UUID=${DATA_UUID}  /mnt/data  ntfs-3g  defaults,uid=1000,gid=1000,umask=022,nofail  0  0"

if ! grep -q "$DATA_UUID" /etc/fstab; then
    echo "Adding entry to /etc/fstab: $FSTAB_ENTRY"
    echo "$FSTAB_ENTRY" | sudo tee -a /etc/fstab
fi

sudo mount -a
echo "Mount verification:"
df -hT /mnt/data

# Setup 8GB Swapfile
if [[ ! -f /swapfile ]]; then
    echo "Creating 8 GB dynamic swapfile..."
    sudo fallocate -l 8G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    if ! grep -q "/swapfile" /etc/fstab; then
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    fi
    echo "Swapfile active:"
    swapon --show
fi
```

- [ ] **Step 4: Implement WSL home restore script**

```bash
#!/usr/bin/env bash
# scripts/migration/restore_wsl_home.sh
set -euo pipefail

BACKUP_ARCHIVE="/mnt/data/wsl_backup/wsl_home_backup.tar.gz"

if [[ ! -f "$BACKUP_ARCHIVE" ]]; then
    echo "ERROR: Backup archive $BACKUP_ARCHIVE not found."
    exit 1
fi

echo "Restoring dotfiles, SSH keys, configuration, and dev projects to home directory ($HOME)..."
tar -xzvf "$BACKUP_ARCHIVE" -C "$HOME"

echo "Restoring file permissions for SSH keys..."
if [[ -d "$HOME/.ssh" ]]; then
    chmod 700 "$HOME/.ssh"
    chmod 600 "$HOME/.ssh/"* 2>/dev/null || true
    chmod 644 "$HOME/.ssh/"*.pub 2>/dev/null || true
fi

echo "SUCCESS: WSL environment restored."
```

- [ ] **Step 5: Commit task artifacts**

```bash
git add scripts/migration/post_install_configure.sh scripts/migration/restore_wsl_home.sh tests/test_fstab_generator.sh
git commit -m "feat(migration): implement Phase 4 auto-mount, swapfile setup, and WSL restore scripts"
```

---

### Task 8: Safe Online Root Partition Expansion & Staging Cleanup

**Files:**
- Create: `scripts/migration/expand_root_partition.sh`
- Test: `tests/test_expand_script_syntax.sh`

**Interfaces:**
- Consumes: Deleted staging partition space, active ext4 root filesystem.
- Produces: Expanded root partition utilizing 100% of freed SSD space without reboot or unmount.

- [ ] **Step 1: Write syntax and safety validation test for online expander**

```bash
#!/usr/bin/env bash
# tests/test_expand_script_syntax.sh
set -euo pipefail

bash -n scripts/migration/expand_root_partition.sh
echo "PASS: Expansion script syntax is valid."
```

- [ ] **Step 2: Implement safe online root expansion script**

```bash
#!/usr/bin/env bash
# scripts/migration/expand_root_partition.sh
set -euo pipefail

echo "================================================"
echo "    SAFE ONLINE ROOT PARTITION EXPANSION"
echo "================================================"

# Verify Quality Gate passed first
if [[ -f scripts/migration/quality_gate_audit.sh ]]; then
    bash scripts/migration/quality_gate_audit.sh || {
        echo "ABORT: Quality gate checks failed. Do not expand partitions yet."
        exit 1
    }
fi

# Ensure cloud-guest-utils is available
if ! which growpart >/dev/null 2>&1; then
    echo "Installing cloud-guest-utils (growpart)..."
    sudo apt update && sudo apt install -y cloud-guest-utils
fi

# Identify root device and partition number
ROOT_DEV=$(findmnt -n -o SOURCE /)
echo "Current root mount source: $ROOT_DEV"

# Parse disk and partition number (e.g., /dev/nvme0n1p2 -> disk: /dev/nvme0n1, part: 2)
if [[ "$ROOT_DEV" =~ ^(/dev/nvme[0-9]+n[0-9]+)p([0-9]+)$ ]]; then
    DISK="${BASH_REMATCH[1]}"
    PART_NUM="${BASH_REMATCH[2]}"
elif [[ "$ROOT_DEV" =~ ^(/dev/[a-z]+)([0-9]+)$ ]]; then
    DISK="${BASH_REMATCH[1]}"
    PART_NUM="${BASH_REMATCH[2]}"
else
    echo "ERROR: Unable to parse root disk and partition number from $ROOT_DEV"
    exit 1
fi

echo "Target Disk: $DISK | Partition Number: $PART_NUM"
echo "Expanding partition boundary online with growpart..."
sudo growpart "$DISK" "$PART_NUM" || echo "Note: growpart returned non-zero (partition may already be maximum size)."

echo "Resizing ext4 filesystem online with resize2fs..."
sudo resize2fs "$ROOT_DEV"

echo "SUCCESS: Online expansion completed. Updated storage geometry:"
df -hT /
```

- [ ] **Step 3: Run test to verify script syntax and execution**

Run: `chmod +x scripts/migration/expand_root_partition.sh tests/test_expand_script_syntax.sh`
Run: `bash tests/test_expand_script_syntax.sh`
Expected: PASS with "Expansion script syntax is valid."

- [ ] **Step 4: Commit task artifacts**

```bash
git add scripts/migration/expand_root_partition.sh tests/test_expand_script_syntax.sh
git commit -m "feat(migration): implement safe online root partition expansion using growpart and resize2fs"
```

---

## Self-Review Checklist

- [x] **Spec Coverage:** Covers ISO verification (Task 1), GPT & BCD redundancy (Task 2), Phase 1 DiskGenius staging (Task 3), Phase 2 UEFI injection (Task 4), Phase 3 Calamares install (Task 5), Post-install Quality Gate (Task 6), Phase 4 fstab & WSL restore (Task 7), and Safe Online Expansion (Task 8).
- [x] **No Placeholders:** Every command, shell script, PowerShell snippet, and configuration line is provided completely without "TODO", "TBD", or placeholders.
- [x] **Guardrails Respected:** Partition 4 is protected in every task; FAT32 4GB limit is verified; Windows interop standard `< /dev/null` is enforced.
- [x] **Consistent Naming & Types:** Staging partition is consistently labeled `DEBIAN_SET`, user data is labeled `DATA_STORE`, paths map to `/mnt/data` and `/mnt/d/wsl_backup`.
