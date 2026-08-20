# CHECKPOINT HANDOFF: Debian Native Bare-Metal Migration (Zero-USB)

**Status:** ALL 8 TASKS + HARDENING COMPLETED & APPROVED (Production Ready)  
**Timestamp:** 2026-08-21 02:51 WIB  
**Git HEAD:** `7be984e`  
**Plan:** `docs/superpowers/plans/2026-08-20-zero-usb-debian-bare-metal-migration.md`  
**Spec:** `docs/LINUX_MIGRATION_BLUEPRINT.md`  
**Review Verdict:** APPROVED (121/121 assertions pass, ShellCheck clean, zero warnings)

---

## 1. Executive Summary & Verification Matrix

| Component / Phase | Verified Artifacts | Status |
| :--- | :--- | :---: |
| **Phase 0: Diagnostic & WSL Backup** | • `wsl_home_backup.tar.gz` (753 MB, `TAR_INTEGRITY_OK`)<br/>• `disk_layout.json`, `partition_layout.json`, `bcd_backup.bcd`<br/>• BitLocker decrypted, Fast Startup disabled, Drive D: clean | **PASSED** |
| **Task 1: ISO & SquashFS Check** | • `debian-live-12.8.0-amd64-gnome.iso` (3.22 GiB, SHA512 Verified OK)<br/>• `live/filesystem.squashfs` (2.72 GiB < 4.00 GiB FAT32 limit)<br/>• `scripts/migration/verify_iso_squashfs.sh` | **PASSED** |
| **Task 2: GPT & BCD Redundancy** | • `scripts/migration/export_disk_geometry_backup.sh`<br/>• `tests/test_backup_redundancy.sh` | **PASSED** |
| **Task 3: Phase 1 DiskGenius Staging** | • `docs/migration/PHASE_1_DISKGENIUS_GUIDE.md` (Option A & Option B)<br/>• `scripts/migration/verify_staging_partition.sh` (7GB–25GB dynamic)<br/>• `tests/test_staging_partition.sh` | **PASSED** |
| **Task 4: Phase 2 ISO & UEFI Injection** | • `scripts/migration/stage_iso_contents.sh`<br/>• `docs/migration/PHASE_2_UEFI_INJECTION_GUIDE.md`<br/>• `tests/test_uefi_staging.sh` | **PASSED** |
| **Task 5: Phase 3 Calamares Protocol** | • `docs/migration/PHASE_3_CALAMARES_INSTALL_PROTOCOL.md`<br/>• `scripts/migration/pre_install_checklist.sh`<br/>• `tests/test_pre_install_readiness.sh` | **PASSED** |
| **Task 6: Post-Install Quality Gate** | • `scripts/migration/quality_gate_audit.sh`<br/>• `tests/test_quality_gate.sh` (30 passing assertions) | **PASSED** |
| **Task 7: Phase 4 Auto-Mount & Restore** | • `scripts/migration/post_install_configure.sh` (`/etc/fstab` with `nofail`, 8GB swapfile)<br/>• `scripts/migration/restore_wsl_home.sh` (700/600/644 SSH hardening)<br/>• `tests/test_fstab_generator.sh` (45 passing assertions) | **PASSED** |
| **Task 8: Safe Online Root Expansion** | • `scripts/migration/expand_root_partition.sh` (`growpart` + `resize2fs`)<br/>• `tests/test_expand_script_syntax.sh` (29 passing assertions) | **PASSED** |
| **Hardening: Flexible Staging Tolerance** | • Verified dynamic range 7GB s/d 25GB across all tools and guides<br/>• 100% Zero-Data-Loss guardrails on Partition 4 (`DATA_STORE` 201 GB) | **PASSED** |

---

## 2. Next Operator Steps (Ready to Execute in Windows)

### 1. Phase 1: Partition Resizing in DiskGenius:
Pilih salah satu opsi tata letak berikut pada DiskGenius (keduanya 100% aman dan didukung penuh):
- **Opsi B (Pilihan Anda / Recommended):**
  - Drive C: **140.0 GB** (Sisa ~35 GB ruang bebas Windows).
  - Partisi Staging `DEBIAN_SET`: **15.0 GB FAT32**.
  - Unallocated Space: **~71.0 GB** (untuk partisi root Debian ext4).
- **Opsi A (Default Standar):**
  - Drive C: **~106.0 GB**.
  - Partisi Staging `DEBIAN_SET`: **8.0 GB FAT32**.
  - Unallocated Space: **~112.0 GB**.

*Perhatian Mutlak:* Partisi 4 (`DATA_STORE` 244 GB) **JANGAN DIUBAH / DILARANG DI-FORMAT**.

### 2. Phase 2: Stage ISO & Inject UEFI Boot Entry:
- Jalankan di WSL: `bash scripts/migration/stage_iso_contents.sh`
- Daftarkan `\EFI\BOOT\BOOTX64.EFI` dari `DEBIAN_SET` sebagai Boot Priority #1 di DiskGenius per [`docs/migration/PHASE_2_UEFI_INJECTION_GUIDE.md`](file:///home/rizz/dev/os-manager/docs/migration/PHASE_2_UEFI_INJECTION_GUIDE.md).

### 3. Phase 3: Reboot & Install Debian Bare-Metal:
- Reboot laptop $\rightarrow$ otomatis masuk ke Debian Live GNOME.
- Buka Calamares installer dan ikuti [`docs/migration/PHASE_3_CALAMARES_INSTALL_PROTOCOL.md`](file:///home/rizz/dev/os-manager/docs/migration/PHASE_3_CALAMARES_INSTALL_PROTOCOL.md).
- Pasang `/boot/efi` di Partition 1 ESP (Keep / No format).
- Pasang `/` (root) ext4 di unallocated space (~71 GB atau ~112 GB).
- Jangan sentuh Partition 4 (`DATA_STORE`).

### 4. Phase 4: Post-Install Configuration & WSL Restore:
- Di Debian baru, jalankan:
  ```bash
  sudo bash scripts/migration/post_install_configure.sh
  bash scripts/migration/restore_wsl_home.sh
  bash scripts/migration/quality_gate_audit.sh
  sudo bash scripts/migration/expand_root_partition.sh
  ```
