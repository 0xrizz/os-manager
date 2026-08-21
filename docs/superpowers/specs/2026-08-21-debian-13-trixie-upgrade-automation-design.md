# Design Specification: Debian 13 (Trixie) Upgrade Automation

- **Target System:** Bare-Metal Debian GNU/Linux (Lenovo IdeaPad 3 / Intel Ice Lake)
- **Document Date:** 2026-08-21 (Revised & SRE Audit Approved)
- **Status:** Approved Production Specification
- **Owner:** os-manager Platform Engineering & SRE

---

## 1. Executive Summary & SRE Reliability Principles

Debian 13 (*Trixie*) introduces modern Linux kernel branches, updated system toolchains (glibc 2.38/2.39+, gcc, python 3.12+), and deb822 repository configurations. On active bare-metal hardware, executing a major distribution upgrade without rigorous controls exposes the host to critical failure modes:

1. **Session Guillotine (Display Manager Restarts):** When `gdm3`, `mutter`, or `systemd-logind` are upgraded in Phase 4, the active Wayland/X11 session restarts, instantly killing parent graphical terminal emulators (GNOME Terminal, Ptyxis, Alacritty) and aborting `dpkg` mid-unpack. **Mitigation:** The upgrade engine enforces execution inside an active `tmux`, `screen`, or pure Linux Virtual Console (`TTY3`).
2. **Zero-Downgrade Reality (The Point of No Return):** Once `dpkg` unpacks upgraded shared libraries (`libc6`, `libsystemd0`), Debian does NOT support automatic downgrades. Attempting to revert APT sources to Bookworm leaves the system with broken dynamic linkers (`ld-linux`) and unresolvable cyclic conflicts. **Mitigation:** A strict Point-of-No-Return gate precedes package unpacking, coupled with an automated emergency `dpkg --configure -a` / `apt-get install -f` recovery protocol and an offline chroot rescue runbook.
3. **Initramfs Storage Explosion:** Generating dual kernel initramfs images (`6.1` and `6.12+`) containing full uncompressed non-free firmware (`firmware-iwlwifi`, `firmware-misc-nonfree`) causes severe transient disk inflation. **Mitigation:** A mandatory pre-flight gate verifies $\ge$ **1.0 GB** of free space in `/boot`.
4. **Python Runtime Decoupling:** Upgrading Python from 3.11 to 3.12+ breaks existing virtual environments (`.venv`) and PEP 668 controls. **Mitigation:** The core upgrade engine (`scripts/upgrade_debian_trixie.sh`) is a 100% zero-dependency POSIX Bash script. The Python CLI (`osm upgrade`) serves only as a high-level wrapper and multiplexer launcher.
5. **deb822 Stanza Standardization:** Debian 13 standardizes on `/etc/apt/sources.list.d/debian.sources` while deprecating legacy one-line `/etc/apt/sources.list`.
6. **Dual Backup Redundancy:** Critical state snapshots (`/etc/apt/`, package manifests, `/etc` tarballs) are mirrored to both `/var/backups/osm/` (Root SSD) and persistent storage `/mnt/data/osm_backups/` (Drive D:).

---

## 2. Hardware & Storage Baseline

- **Model:** Lenovo IdeaPad 3 (81WD) / Intel Core i5-1035G1 (Ice Lake)
- **Active Distribution:** Debian GNU/Linux 12.15 (Bookworm) $\rightarrow$ Debian 13 (Trixie)
- **Active Kernel:** Linux 6.1.0-52-amd64
- **Root Filesystem (`/`):** `/dev/nvme0n1p2` (ext4, ~228 GB, >190 GB free)
- **Boot Directory (`/boot`):** Dedicated headroom $\ge$ 1.0 GB verified before execution
- **EFI Partition (`/boot/efi`):** `/dev/nvme0n1p1` (vfat, 96 MB, ~62 MB free)
- **Persistent Data (`/mnt/data`):** `/dev/nvme0n1p4` (NTFS, 244.1 GB, protected persistent storage)
- **Wi-Fi Controller:** Intel Ice Lake-LP PCH CNVi WiFi (Intel AC 9560 / `iwlwifi`, requiring `firmware-iwlwifi`)
- **Audio Controller:** Intel Ice Lake-LP Smart Sound Technology (`snd_hda_intel` / `snd_sof`)
- **Graphics (GPU):** Intel Iris Plus Graphics G1 (`i915`) & NVIDIA GeForce MX330 (`nouveau`)

---

## 3. Architecture & Execution Pipeline

The upgrade workflow consists of 6 sequential phases with strict transition boundaries:

```
[Phase 0: Pre-Flight Safety Gate]
       │ (Verify root, tmux/screen, /boot >= 1GB, / >= 10GB, network, dpkg locks)
       ▼
[Phase 1: Dual State Backup & Tarball Snapshot]
       │ (Mirror /etc/apt/, manifests, /etc archive to /var/backups and /mnt/data)
       ▼
[Phase 2: deb822 Repository Matrix Transition]
       │ (Write debian.sources with non-free-firmware; clear legacy sources.list)
       ▼
╔═══════════════════════════════════════════════════════════════╗
║               POINT OF NO RETURN (User Gate)                  ║
║   (Explicit confirmation that package unpacking is permanent) ║
╚═══════════════════════════════════════════════════════════════╝
       │
       ▼
[Phase 3: Minimal Safe Upgrade] ──(Failure)──► [Emergency chroot / dpkg repair]
       │ (--without-new-pkgs, non-interactive debconf)
       ▼
[Phase 4: Full Distribution Upgrade] ──(Failure)──► [Emergency chroot / dpkg repair]
       │ (full-upgrade, autoremove, clean)
       ▼
[Phase 5: Post-Upgrade Hardware Audit & Venv Rebuild]
         (Audit Wi-Fi/Audio/DRM/systemd, rebuild Python 3.12 .venv)
```

### Phase 0: Pre-Flight Safety Gate
- **Root Enforcement:** Require `EUID == 0` or execution via `sudo`.
- **Enclave Protection:** Verify execution inside an active `tmux` (`$TMUX`), `screen` (`$STY`), or Linux virtual console (`/dev/tty[1-6]`). Abort if executed in a naked graphical terminal emulator unless `--allow-unattached` is explicitly supplied.
- **Storage Headroom:**
  - Root filesystem (`/`): minimum **10 GB** (10,485,760 KB) free.
  - Boot storage (`/boot`): minimum **1.0 GB** (1,048,576 KB) free to guarantee dual initramfs generation.
  - EFI partition (`/boot/efi`): minimum **20 MB** (20,480 KB) free if present.
- **Network Probe:** Verify DNS and HTTP reachability to `deb.debian.org`.
- **DPKG Consistency:** Assert `dpkg --audit` returns 0 errors, verify no held packages, and assert zero active `/var/lib/dpkg/lock*` or `/var/lib/apt/lists/lock` locks.

### Phase 1: Dual State Backup & Tarball Snapshot
- **Primary Backup:** Create `/var/backups/osm/apt_pre_trixie_<timestamp>/` containing:
  - Recursive copy of `/etc/apt/` (including all `.sources`, `.list`, and keyrings).
  - Tarball archive of `/etc` configuration: `etc_config_snapshot.tar.gz`.
  - Package selections: `dpkg --get-selections > dpkg_selections.txt`.
  - Manual package markings: `apt-mark showmanual > apt_manual_pkgs.txt`.
  - Telemetry metadata: `upgrade_manifest.json`.
- **Redundant Secondary Backup:** If `/mnt/data` is mounted and writable, copy the entire backup bundle to `/mnt/data/osm_backups/apt_pre_trixie_<timestamp>/` to protect against root drive corruption.

### Phase 2: deb822 Repository Matrix Transition
- **Target File:** `/etc/apt/sources.list.d/debian.sources`
- **Format:** deb822 multi-stanza format:
  ```text
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
  ```
- **Legacy Cleanup:** Overwrite `/etc/apt/sources.list` with a comment notice to eliminate duplicate target warnings.
- **Third-Party Disabling:** Temporarily disable `/etc/apt/sources.list.d/*.list` (renaming to `*.disabled_for_upgrade`).

### Point of No Return & Failure Protocol
- **Gate:** Before beginning package unpacking in Phase 3, the engine requires explicit user confirmation (or `--non-interactive`).
- **Emergency Repair Protocol:** If an error occurs during package installation, the script runs:
  1. `dpkg --configure -a` to complete partially configured packages.
  2. `apt-get install -f -y` to satisfy broken dependency trees.
- **Manual Chroot Emergency Rescue Runbook:**
  If a catastrophic power loss or system crash occurs mid-unpack, recover via live rescue USB:
  ```bash
  sudo mount /dev/nvme0n1p2 /mnt
  sudo mount /dev/nvme0n1p1 /mnt/boot/efi
  for i in /dev /dev/pts /proc /sys /run; do sudo mount --bind $i /mnt$i; done
  sudo chroot /mnt
  dpkg --configure -a
  apt-get update && apt-get install -f -y
  update-initramfs -u -k all
  update-grub
  exit
  sudo reboot
  ```

### Phase 3: Minimal Safe Upgrade
- Synchronize indexes: `apt-get update`.
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

### Phase 5: Post-Upgrade Verification & Runtime Venv Rebuild
- **Hardware & Systemd Audit:**
  - OS Release codename (`trixie`) & Kernel version (`uname -r`).
  - Intel AC 9560 / CNVi Wi-Fi (`iwlwifi` module and active interface).
  - Intel SST Audio controller (`/proc/asound/cards`).
  - Intel Iris Plus & NVIDIA MX330 GPU initialization.
  - Zero degraded systemd services (`systemctl --failed`).
- **Python Virtualenv Rebuild:**
  - Subcommand `osm upgrade rebuild-venv` purges outdated Python 3.11 `.venv` folders and rebuilds clean environments with Python 3.12+.

---

## 4. Component Structure & CLI Specification

1. **Standalone Engine Script:** [`scripts/upgrade_debian_trixie.sh`](file:///home/rizz/dev/os-manager/scripts/upgrade_debian_trixie.sh)
   - Zero Python dependency; 100% Bash 4.4+ POSIX utilities.
   - Flags: `--check`, `--dry-run`, `--backup-only`, `--apply`, `--verify`, `--allow-unattached`, `--non-interactive`.
2. **CLI Wrapper Router:** [`os_manager/commands/upgrade.py`](file:///home/rizz/dev/os-manager/os_manager/commands/upgrade.py)
   - Integrated into `osm upgrade` (`check`, `dry-run`, `start`, `verify`, `rebuild-venv`).
   - Automatically wraps execution inside a dedicated `tmux` session (`osm-trixie-upgrade`) if invoked from an unattached terminal.

---

## 5. Safety Guardrails & Zero-Data-Loss Invariants

1. **Persistent Partition Invariance:** `/dev/nvme0n1p4` (`/mnt/data`) is never formatted, resized, or altered.
2. **Enclave Invariance:** No upgrade execution without active `tmux`/`screen`/TTY3 protection unless `--allow-unattached` is explicitly provided.
3. **Firmware Retention Invariance:** `non-free-firmware` is mandatory across all generated deb822 stanzas.
4. **Boot Headroom Invariance:** `/boot` must maintain $\ge$ 1.0 GB free space before package operations begin.
