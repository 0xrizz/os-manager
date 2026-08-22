# System Design Specification: HSI Device Security Hardening

**Target System:** Lenovo 81WD (Intel Core i5-1035G1 Ice Lake) | Debian GNU/Linux 13 (Trixie)  
**Date:** 2026-08-22  
**Status:** Approved for Implementation  
**Auditor / Tool:** `fwupd` v2.0.20 (Host Security ID / HSI Standard)

---

## 1. Executive Summary & Problem Statement

An audit performed via `fwupdmgr security` generated an overall rating of **`HSI:0!`** on the target Lenovo 81WD bare-metal Linux environment. While fundamental protections like UEFI Secure Boot, TPM 2.0, IOMMU DMA Protection, and Kernel Lockdown are active, the system reported critical failures in key firmware, storage, and power management domains:

1. **`UEFI db: ! Fail (Not Valid)`**: The Secure Boot signature database lacks the latest DBX revocation entries.
2. **`Intel Management Engine Version: ! Fail (Not Valid)`**: Intel ME firmware requires an updated patch version from LVFS or vendor release.
3. **`Linux Swap: ! Fail (Not Encrypted)`**: System swap is hosted on unencrypted persistent NVMe storage, allowing potential forensic memory extraction.
4. **`Suspend To RAM: ! Fail (Enabled)` / `Suspend To Idle: ! Fail (Not Enabled)`**: The system defaults to ACPI S3 sleep state rather than modern S0ix (`s2idle`), leaving physical RAM vulnerable to cold-boot extraction attacks.

This specification outlines the technical design for a comprehensive, zero-risk hardening workflow to remediate these findings and elevate the HSI security posture.

---

## 2. Goals & Non-Goals

### Goals
* Remediate `UEFI db` by applying the latest Secure Boot DBX revocation list via `fwupdmgr`.
* Query and apply official Intel ME / BIOS updates if available on LVFS.
* Eliminate unencrypted swap by configuring volatile in-memory compressed swap (`systemd-zram-generator` with `zstd`) and decommissioning plaintext swap entries in `/etc/fstab`.
* Reconfigure the Linux kernel default sleep state to `s2idle` via GRUB cmdline configuration.
* Provide non-destructive, verifiable rollback mechanisms for all configuration changes.

### Non-Goals
* Hardware modification for silicon-limited features: Intel CET (Control-flow Enforcement Technology) and Encrypted RAM (Total Memory Encryption) are not supported on 10th Gen Intel Core CPUs and will remain marked as informational constraints.
* Re-partitioning or destructive filesystem operations (strictly adhering to Zero-Data-Loss guardrails).

---

## 3. Architecture & Subsystem Design

```
+-----------------------------------------------------------------------------------+
|                            fwupdmgr security Audit                                |
+-----------------------------------------------------------------------------------+
         |                                |                               |
         v                                v                               v
+------------------+           +----------------------+         +-------------------+
|  Firmware & DBX  |           |   Volatile Memory    |         |    Kernel ACPI    |
|   Hardening      |           |    Swap Hardening    |         |    Sleep State    |
+------------------+           +----------------------+         +-------------------+
| • fwupdmgr       |           | • systemd-zram-      |         | • GRUB cmdline:   |
|   refresh        |           |   generator          |         |   mem_sleep_      |
| • Apply UEFI dbx |           | • zram0 (zstd, ram/2)|         |   default=s2idle  |
| • Check LVFS for |           | • Deactivate un-     |         | • Protect against |
|   Lenovo ME/BIOS |           |   encrypted fstab    |         |   cold-boot RAM   |
|   updates        |           |   disk swap          |         |   extraction      |
+------------------+           +----------------------+         +-------------------+
         \                                |                              /
          \_______________________________|_____________________________/
                                          |
                                          v
                   +-----------------------------------------------+
                   |   Verified Enhanced HSI Security Assessment   |
                   +-----------------------------------------------+
```

---

## 4. Technical Implementation Specifications

### 4.1 Subsystem 1: Firmware & Secure Boot DBX Update
* **Utility:** `fwupd` / `fwupdmgr`
* **Execution Flow:**
  1. `sudo fwupdmgr refresh` to synchronize metadata with the Linux Vendor Firmware Service (LVFS).
  2. `sudo fwupdmgr get-updates` to query available updates for UEFI DBX, System Firmware, and Intel Management Engine.
  3. `sudo fwupdmgr update` to download and stage firmware payloads for next reboot.

### 4.2 Subsystem 2: Volatile In-Memory Swap Architecture
* **Package:** `systemd-zram-generator`
* **Configuration File:** `/etc/systemd/zram-generator.conf`
* **Configuration Content:**
  ```ini
  [zram0]
  zram-size = min(ram / 2, 8192)
  compression-algorithm = zstd
  swap-priority = 100
  ```
* **Storage Swap Decommissioning:**
  * Backup `/etc/fstab` to `/etc/fstab.bak.<timestamp>`.
  * Safely comment out any active unencrypted swap partition lines (`/dev/nvme0n1p...` or swapfiles).
  * Run `swapoff -a` followed by starting `systemd-zram-setup@zram0.service` and `swapon -a`.

### 4.3 Subsystem 3: Kernel Sleep Mode Hardening
* **Target File:** `/etc/default/grub`
* **Configuration:**
  * Append `mem_sleep_default=s2idle` to `GRUB_CMDLINE_LINUX_DEFAULT`.
  * Run `sudo update-grub` to regenerate `/boot/grub/grub.cfg`.
* **Runtime Verification:**
  * `cat /sys/power/mem_sleep` must indicate `[s2idle] deep`.

---

## 5. Risk Assessment, Safety & Rollback Plan

| Subsystem | Potential Failure / Risk | Rollback Procedure |
| :--- | :--- | :--- |
| **zRAM Swap** | Memory pressure under extreme compilation tasks | Restore `/etc/fstab` from backup, remove `/etc/systemd/zram-generator.conf`, restart swap daemon. |
| **Kernel Sleep** | Increased standby battery consumption on suspend | Remove `mem_sleep_default=s2idle` from `/etc/default/grub` and run `sudo update-grub`. |
| **Firmware / DBX** | Interrupted firmware staging | Handled natively by UEFI Capsule update checksums and fallback rollback in firmware. |

---

## 6. Verification & Acceptance Criteria

1. **Swap Verification:**
   * Command: `swapon --show`
   * Requirement: Displays `/dev/zram0` as the sole active swap device with priority `100`. No plaintext disk partitions mounted as swap.
2. **Power State Verification:**
   * Command: `cat /sys/power/mem_sleep`
   * Requirement: `[s2idle]` is the active selection.
3. **Security Audit Verification:**
   * Command: `fwupdmgr security`
   * Requirement:
     * `UEFI db`: Pass (Valid)
     * `Linux Swap`: Pass (Encrypted / Volatile zRAM)
     * `Suspend To Idle`: Pass (Enabled)
     * Overall HSI score improvement.
