# Design Specification: Debian 13 (Trixie) Upgrade Automation

- **Target System:** Bare-Metal Debian GNU/Linux (Lenovo IdeaPad 3 / Intel Ice Lake)
- **Document Date:** 2026-08-21 (Revised)
- **Status:** Approved Architecture Specification
- **Owner:** os-manager Platform Engineering & SRE

---

## 1. Executive Summary & Reliability Principles

Debian 13 (*Trixie*) introduces upgraded Linux kernel series, updated system toolchains (glibc, gcc, python 3.12+), and modernized package configurations. On active bare-metal hardware, upgrading a major OS distribution involves distinct failure modes:
1. **Display Manager Termination:** GNOME/Wayland/GDM3 restarts during package unpacking kill parent terminal processes if not guarded inside a multiplexer (`tmux`/`screen`).
2. **Point of No Return (Zero-Downgrade Reality):** Official Debian release engineering does not support automated downgrades once `dpkg` begins unpacking upgraded core packages (`glibc`, `systemd`). Downgrading APT source files mid-upgrade causes fatal ABI mismatches.
3. **Kernel Initramfs Bloat:** Regenerating multiple initramfs images containing uncompressed non-free firmware (`firmware-iwlwifi`, `firmware-misc-nonfree`) requires significant headroom in `/boot`.
4. **Runtime Venv Invalidation:** Upgrading Python from 3.11 to 3.12+ immediately breaks existing Python virtualenvs (`.venv`). The core upgrade engine must therefore be a standalone, zero-dependency Bash script.
5. **deb822 Repository Format:** Debian 13 standardizes on the deb822 stanza format in `/etc/apt/sources.list.d/debian.sources`.

---

## 2. System Context & Hardware Baseline

- **Distribution:** Debian GNU/Linux 12.15 (Bookworm) $\rightarrow$ Debian 13 (Trixie)
- **Active Kernel:** Linux 6.1.0-52-amd64
- **Root Partition (`/`):** `/dev/nvme0n1p2` (ext4, ~228 GB, >190 GB free)
- **Boot Storage (`/boot`):** Part of root filesystem, requires $\ge$ 1 GB dedicated headroom for dual initramfs generation.
- **EFI System Partition (`/boot/efi`):** `/dev/nvme0n1p1` (vfat, 96 MB, ~62 MB free).
- **Persistent Data (`/mnt/data`):** `/dev/nvme0n1p4` (NTFS, 244.1 GB, protected persistent storage).
- **Wi-Fi Controller:** Intel Ice Lake-LP PCH CNVi WiFi (Intel AC 9560 / `iwlwifi`, requiring `firmware-iwlwifi`).
- **Audio Controller:** Intel Ice Lake-LP Smart Sound Technology (`snd_hda_intel` / `snd_sof`).
- **Display Controllers:** Intel Iris Plus Graphics G1 (`i915`) & NVIDIA GeForce MX330 (`nouveau`).

---

## 3. Architecture & Execution Pipeline

The upgrade pipeline is structured into 6 strict sequential phases:

```
[Phase 0: Pre-Flight Gate]
       │
       ▼
[Phase 1: State Backup & Tarball Snapshot]
       │
       ▼
[Phase 2: deb822 Source Transition]
       │
       ▼
╔═══════════════════════════════════════════════╗
║       POINT OF NO RETURN (User Gate)          ║
╚═══════════════════════════════════════════════╝
       │
       ▼
[Phase 3: Minimal Safe Upgrade] ──(Failure)──► [Emergency chroot / dpkg repair]
       │
       ▼
[Phase 4: Full Distribution Upgrade]
       │
       ▼
[Phase 5: Post-Upgrade Audit & Venv Rebuild]
```

### Phase 0: Pre-Flight Verification Gate
- **Root Enforcement:** Require `EUID == 0` or execution via `sudo`.
- **Multiplexer Protection:** Verify execution inside an active `tmux` (`$TMUX`) or `screen` (`$STY`) session. Refuse execution in raw graphical terminals unless explicitly overridden by `--allow-unattached`.
- **Storage Headroom:**
  - Root filesystem (`/`): minimum **10 GB** (10,485,760 KB) free.
  - Boot filesystem (`/boot`): minimum **1 GB** (1,048,576 KB) free to ensure generation of both fallback and target kernel initramfs.
  - EFI partition (`/boot/efi`): minimum **20 MB** (20,480 KB) free.
- **Network Probe:** Verify DNS and HTTP reachability to `deb.debian.org` and `security.debian.org`.
- **Package Consistency & Locks:** Assert `dpkg --audit` has zero errors, verify no `hold` packages, and confirm no active `apt`/`dpkg` locks.

### Phase 1: State Backup & Tarball Snapshot
- **Configuration Snapshot:** Create `/var/backups/osm/apt_pre_trixie_<timestamp>/` containing:
  - Recursive copy of `/etc/apt/` (including all `.sources`, `.list`, `.list.d/`, and `.gpg` keyrings).
  - Package selections manifest: `dpkg --get-selections > dpkg_selections.txt`.
  - Manual package markings: `apt-mark showmanual > apt_manual_pkgs.txt`.
  - System telemetry: `upgrade_manifest.json`.
- **Root Config Archive:** Create a tarball snapshot of `/etc` (`/var/backups/osm/etc_pre_trixie_<timestamp>.tar.gz`) for disaster recovery.

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
- **Legacy Cleanup:** Empty or backup legacy `/etc/apt/sources.list` to prevent duplicate target warnings.
- **Third-Party Handling:** Temporarily disable `/etc/apt/sources.list.d/*.list` (renaming to `*.disabled_for_upgrade`).

### Point of No Return & Failure Protocol
- **Gate:** Before beginning package unpacking in Phase 3, the script confirms that user data is backed up and warns that downgrading is unsupported.
- **Failure Handling:** If an error occurs after package unpacking starts, the engine DOES NOT attempt to downgrade APT sources. Instead, it enters the **Emergency Repair Protocol**:
  1. Runs `dpkg --configure -a` to resolve partially configured packages.
  2. Runs `apt-get install -f -y` to fix broken dependencies.
  3. Displays chroot repair instructions if network or reboot fails.

### Phase 3: Minimal Safe Upgrade
- Synchronize package indexes: `apt-get update`.
- Execute staged minimal upgrade to resolve core system packages without mass deletions:
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
- **Hardware Audit:**
  - OS Release codename (`trixie`) & Kernel version.
  - Intel AC 9560 / CNVi Wi-Fi (`iwlwifi` module and active interface).
  - Intel SST Audio controller (`/proc/asound/cards`).
  - Intel Iris Plus & NVIDIA MX330 GPU initialization.
  - Zero degraded systemd services (`systemctl --failed`).
- **Python Virtualenv Rebuild:**
  - Detect outdated `.venv` with mismatched Python version.
  - Automatically rebuild virtualenv with system Python 3.12+ and reinstall repository dependencies.

---

## 4. Component Structure & CLI Specification

1. **Standalone Engine Script:** [`scripts/upgrade_debian_trixie.sh`](file:///home/rizz/dev/os-manager/scripts/upgrade_debian_trixie.sh)
   - Zero Python dependency; purely Bash 4.4+ POSIX utilities.
   - Flags: `--check`, `--dry-run`, `--backup-only`, `--apply`, `--verify`, `--allow-unattached`.
2. **CLI Wrapper Router:** [`os_manager/commands/upgrade.py`](file:///home/rizz/dev/os-manager/os_manager/commands/upgrade.py)
   - Integrates into `osm upgrade` (`check`, `dry-run`, `start`, `verify`, `rebuild-venv`).
   - Automatically wraps execution in a `tmux` session if the user invokes `osm upgrade start` from an unattached terminal.

---

## 5. Safety Guardrails & Zero-Data-Loss Invariants

1. **Persistent Partition Invariance:** `/dev/nvme0n1p4` (`/mnt/data`) is never formatted, resized, or altered.
2. **Multiplexer Invariance:** No upgrade execution without active `tmux`/`screen` protection unless `--allow-unattached` is explicitly provided.
3. **Firmware Retention Invariance:** `non-free-firmware` is mandatory across all generated deb822 stanzas.
