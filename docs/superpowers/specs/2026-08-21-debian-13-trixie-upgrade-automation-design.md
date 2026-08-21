# Design Specification: Debian 13 (Trixie) Upgrade Automation

- **Target System:** Bare-Metal Debian GNU/Linux (Ice Lake / Lenovo Laptop)
- **Document Date:** 2026-08-21
- **Status:** Draft / Pending Implementation Plan
- **Owner:** os-manager Platform Engineering

---

## 1. Executive Summary & Objectives

Debian 13 (*Trixie*) brings upgraded Linux kernel releases, newer toolchains (gcc, glibc, python, node), and modernized package dependencies compared to Debian 12 (*Bookworm*). However, performing a major OS distribution upgrade on active bare-metal hardware carries potential risks of broken dependencies, corrupted package indexes, interrupted network downloads, and driver regressions (especially Wi-Fi firmware, audio, and display servers).

This specification defines the architecture, automated tooling, guardrails, and validation protocols for an automated in-place upgrade pipeline integrated into the `os-manager` ecosystem (`osm upgrade`).

### Key Goals:
1. **Automated Pre-Flight Verification:** Ensure the host environment meets all disk, network, and package health criteria before any system modification.
2. **State Backup & Auto-Rollback:** Back up `/etc/apt/` state and package selections with automatic rollback capability if repository updates fail.
3. **Firmware & Hardware Protection:** Maintain `non-free-firmware` repository components so that critical hardware interfaces (Intel `iwlwifi`, Intel SST Audio, Intel/NVIDIA DRM) remain fully functional.
4. **Interactive CLI & Dry-Run Support:** Expose clear, discoverable subcommands in `osm upgrade` with `--dry-run` and `--check` modes.
5. **Post-Upgrade Hardware Audit:** Execute comprehensive hardware and systemd health verification after system reboot.

### Non-Goals:
- Modifying or re-partitioning the persistent `/mnt/data` drive (Zero-Data-Loss Guardrail).
- Performing destructive formatting of the root partition `/dev/nvme0n1p2`.
- Replacing existing system initialization or altering bootloader architectures beyond standard Debian kernel grub hooks.

---

## 2. System Context & Hardware Baseline

The current bare-metal environment is characterized as follows:
- **Distribution:** Debian GNU/Linux 12.15 (Bookworm)
- **Active Kernel:** Linux 6.1.0-52-amd64
- **Root Partition (`/`):** `/dev/nvme0n1p2` (ext4, ~228 GB, 26 GB used, >190 GB free)
- **EFI Partition (`/boot/efi`):** `/dev/nvme0n1p1` (vfat, 96 MB, 35 MB used, ~62 MB free)
- **Persistent Data (`/mnt/data`):** `/dev/nvme0n1p4` (fuseblk/NTFS, preserved persistent storage)
- **Wi-Fi Controller:** Intel Corporation Ice Lake-LP PCH CNVi WiFi (`iwlwifi` requiring `firmware-iwlwifi`)
- **Audio Controller:** Intel Corporation Ice Lake-LP Smart Sound Technology (`snd_hda_intel` / `snd_sof`)
- **Display Controllers:** Intel Corporation Iris Plus Graphics G1 (`i915`) & NVIDIA GP108M [GeForce MX330] (`nouveau`)

---

## 3. Architecture & Execution Pipeline

The upgrade workflow consists of 6 sequential phases with strict transition boundaries:

```
[Phase 0: Pre-Flight Gate] ──► [Phase 1: Backup & Snapshot] ──► [Phase 2: Source Matrix Transition]
           │                                                                    │
           ▼ (Failure: Safe Abort)                                              ▼
[Phase 5: Post-Upgrade Audit] ◄── [Phase 4: Full-Upgrade] ◄─── [Phase 3: Minimal Safe Upgrade]
```

### Phase 0: Pre-Flight Verification Gate
- **Root Execution:** Verify `EUID == 0` or execute via `sudo`.
- **Disk Storage Headroom:**
  - Root partition (`/`): minimum 10 GB free space required.
  - EFI partition (`/boot/efi`): minimum 20 MB free space required.
- **Network Connectivity:** Probe DNS and HTTPS reachability to `deb.debian.org` and `security.debian.org`.
- **Package Integrity Audit:** Verify that `dpkg --audit` returns 0 broken packages, check for conflicting held packages (`dpkg --get-selections | grep hold`), and ensure no active `apt` locks (`/var/lib/apt/lists/lock`, `/var/lib/dpkg/lock-frontend`).

### Phase 1: State Backup & Snapshot
- **Configuration Snapshot:** Copy `/etc/apt/` recursively to `/var/backups/osm/apt_pre_trixie_<timestamp>/`.
- **Package Manifest Export:** Save installed package selections:
  - `dpkg --get-selections > /var/backups/osm/apt_pre_trixie_<timestamp>/dpkg_selections.txt`
  - `apt-mark showmanual > /var/backups/osm/apt_pre_trixie_<timestamp>/apt_manual_pkgs.txt`
- **Metadata Log:** Write timestamp, kernel version, and pre-flight telemetry to `upgrade_manifest.json`.

### Phase 2: APT Source Matrix Transition
- **Target File:** `/etc/apt/sources.list`
- **Suite Transition:**
  ```text
  deb http://deb.debian.org/debian trixie main contrib non-free non-free-firmware
  deb-src http://deb.debian.org/debian trixie main contrib non-free non-free-firmware

  deb http://deb.debian.org/debian trixie-updates main contrib non-free non-free-firmware
  deb-src http://deb.debian.org/debian trixie-updates main contrib non-free non-free-firmware

  deb http://security.debian.org/debian-security/ trixie-security main contrib non-free non-free-firmware
  deb-src http://security.debian.org/debian-security/ trixie-security main contrib non-free non-free-firmware

  deb http://deb.debian.org/debian trixie-backports main contrib non-free non-free-firmware
  deb-src http://deb.debian.org/debian trixie-backports main contrib non-free non-free-firmware
  ```
- **Third-Party Handling:** Temporarily disable unsupported external repo lists in `/etc/apt/sources.list.d/*.list` (renaming to `.list.disabled_for_upgrade`).

### Phase 3: Minimal Safe Upgrade
- Execute `apt-get update`. If update fails (exit code $\neq 0$), immediately execute automatic rollback to the Phase 1 backup.
- Execute staged minimal upgrade:
  ```bash
  DEBIAN_FRONTEND=noninteractive apt-get upgrade --without-new-pkgs -y \
    -o Dpkg::Options::="--force-confdef" \
    -o Dpkg::Options::="--force-confold"
  ```

### Phase 4: Full Distribution Upgrade
- Execute complete distribution upgrade:
  ```bash
  DEBIAN_FRONTEND=noninteractive apt-get full-upgrade -y \
    -o Dpkg::Options::="--force-confdef" \
    -o Dpkg::Options::="--force-confold"
  ```
- Clean unneeded orphaned packages: `apt-get autoremove --purge -y`.
- Clean download caches: `apt-get clean`.

### Phase 5: Post-Upgrade Verification & Hardware Audit
- Executed automatically or manually via `osm upgrade verify` after reboot.
- Evaluates:
  1. Operating system codename (`trixie`) and kernel version.
  2. Wi-Fi interface state (`ip link show` and `dmesg | grep iwlwifi`).
  3. Audio device detection (`aplay -l` and PipeWire/PulseAudio daemons).
  4. Display driver initialization (`lspci -k` for `i915` and `nouveau`).
  5. Systemd failed unit audit (`systemctl --failed --no-pager`).

---

## 4. Component Structure & CLI Specification

### 1. Engine Script: `scripts/upgrade_debian_trixie.sh`
- CLI flags:
  - `--check`: Runs Phase 0 pre-flight checks and exits.
  - `--dry-run`: Runs Phase 0, creates a temporary APT configuration in `/tmp/osm_apt_sim/`, and executes `apt-get -s dist-upgrade` without modifying system files.
  - `--backup-only`: Runs Phase 1 backup and exits.
  - `--apply`: Executes full Phase 0 to Phase 4 upgrade pipeline.
  - `--rollback`: Restores `/etc/apt/` from the most recent backup in `/var/backups/osm/`.
  - `--verify`: Executes Phase 5 post-upgrade hardware and system audit.

### 2. Python CLI: `os_manager/commands/upgrade.py` & `os_manager/cli.py`
Exposes the Click command group `osm upgrade`:
- `osm upgrade check`: Pre-flight system readiness verification.
- `osm upgrade dry-run`: Dependency simulation without system mutations.
- `osm upgrade start [--non-interactive]`: Initiates full upgrade with user confirmation prompts.
- `osm upgrade rollback-apt`: Reverts APT sources to previous Bookworm backup.
- `osm upgrade verify`: Executes post-upgrade hardware diagnostics.

---

## 5. Safety Guardrails & Error Handling

1. **Signal Trapping:** `scripts/upgrade_debian_trixie.sh` sets `trap cleanup EXIT INT TERM` to release any transient lockfiles and reset terminal echo.
2. **Debconf Automation:** Non-interactive execution prevents unattended terminal hangs on configuration file differences.
3. **Partition Immutability:** `/dev/nvme0n1p4` (`/mnt/data`) is never unmounted, resized, or touched during the upgrade routine.
4. **Apt Update Failure Fallback:** If mirror synchronization fails after switching sources, the script automatically reverts `/etc/apt/sources.list` to Bookworm and runs `apt-get update` to restore system health.

---

## 6. Testing & Validation Plan

### Unit Testing (`tests/test_upgrade_command.py`):
- Test Click CLI command registration and option parsing.
- Mock underlying bash script executions and verify CLI exit code handling.
- Verify `--json` and standard terminal output formatters.

### Integration / Dry-Run Testing:
- Execute `osm upgrade check` on the active host and assert that all checks pass (disk space, network, package consistency).
- Execute `osm upgrade dry-run` to verify APT simulation mechanics without affecting live `/etc/apt/` files.
- Verify backup directory generation and restoration in `/var/backups/osm/`.

### Post-Upgrade Acceptance Criteria:
1. `cat /etc/os-release` confirms `VERSION_CODENAME=trixie`.
2. Wireless interface connects to local access point without firmware errors.
3. Audio output is functional across system speakers / headphones.
4. `systemctl --failed` reports 0 failed services.
