# Design Specification: Debian 13 (Trixie) Upgrade Automation

- **Target System:** Bare-Metal Debian GNU/Linux (Lenovo IdeaPad 3 / Intel Ice Lake)
- **Document Date:** 2026-08-21 (Hardened SRE & Hardware Firmware Remediated)
- **Status:** Approved Production Specification
- **Owner:** os-manager Platform Engineering & SRE

---

## 1. Executive Summary & SRE Reliability Principles

Debian 13 (*Trixie*) introduces modern Linux kernel branches (Linux 6.12+), updated system toolchains (glibc 2.38/2.39+, gcc, python 3.12+), and deb822 repository configurations. On active bare-metal hardware, executing a major distribution upgrade without rigorous controls exposes the host to critical physical, kernel subsystem, power-state, and firmware failure modes:

1. **Session Guillotine (Display Manager Restarts):** When `gdm3`, `mutter`, or `systemd-logind` are upgraded in Phase 4, the active Wayland/X11 session restarts, instantly killing parent graphical terminal emulators (GNOME Terminal, Ptyxis, Alacritty) and aborting `dpkg` mid-unpack. **Mitigation:** The upgrade engine enforces execution inside an active `tmux`, `screen`, or pure Linux Virtual Console (`TTY3`), with automatic CLI bootstrap and installation of `tmux` if missing.
2. **ACPI Sleep & Laptop Lid Switch Traps:** Closing the laptop lid or reaching idle timeout triggers `systemd-logind` suspend (`HandleLidSwitch=suspend`). Entering ACPI S0ix / S3 mid-upgrade stalls NVMe APST DMA queues, corrupting dynamic linkers and in-flight ext4 transactions. **Mitigation:** The upgrade script self-wraps via `systemd-inhibit --what=sleep:idle:shutdown:handle-lid-switch --why="Debian 13 Upgrade" --mode=block` when running as root.
3. **Power Delivery & Battery Exhaustion:** Running a dist-upgrade on battery risks sudden thermal power-off mid-glibc unpack. **Mitigation:** Mandatory Phase 0 pre-flight check asserting active AC power adapter connection (`on_ac_power` or sysfs power supply probe).
4. **Debconf & Needrestart Terminal Stalls:** Major upgrades invoke `needrestart` and `grub-efi-amd64` prompts. Unattended executions freeze or fail with DPkg status 1. **Mitigation:** Pre-seeding of `grub2/force_efi_extra_removable` and `grub-efi/install_devices`, and global export of `NEEDRESTART_MODE=a`, `NEEDRESTART_SUSPEND=1`, `DEBIAN_FRONTEND=noninteractive`, and `UCF_FORCE_CONFFOLD=1`.
5. **Memory Pressure & Initramfs Compression OOM Killer:** Multi-threaded `zstd -T0` compression during `update-initramfs` combined with `dpkg` memory allocations can trigger kernel OOM killer / `systemd-oomd`, delivering uncatchable `SIGKILL` and leaving a corrupt 0-byte initramfs. **Mitigation:** Enforce Phase 0 virtual memory headroom (`MemAvailable + SwapTotal >= 2048 MB`), adjust `/proc/$$/oom_score_adj` to `-1000`, and constrain compression concurrency if physical RAM is constrained.
6. **UEFI Secure Boot & Kernel Lockdown Invariants:** Linux 6.12+ enforces kernel lockdown under UEFI Secure Boot, rejecting unsigned DKMS modules (such as NVIDIA MX330) and unverified firmware. **Mitigation:** Audit `mokutil --sb-state` in Phase 0, stage MOK enrollment via `mokutil --import`, log MokManager EFI instructions for post-reboot enrollment, and audit `/sys/kernel/security/lockdown` in Phase 5.
7. **Sound Open Firmware (SOF) Hardware Silence:** Kernel 6.12+ on Intel Ice Lake (1035G1) defaults strictly to Sound Open Firmware (`snd_sof_pci_intel_icl`), deprecating legacy HDA fallbacks. **Mitigation:** Explicit queueing and installation of `firmware-sof-signed`, `firmware-misc-nonfree`, and `alsa-ucm-conf` alongside `firmware-iwlwifi`, with Phase 5 verification checking kernel driver dmesg binding.
8. **NetworkManager Keyfile Migration & Permissions:** Debian 13 NetworkManager strictly enforces `0600` permissions on `/etc/NetworkManager/system-connections/*.nmconnection` keyfiles. Non-conforming permissions cause silent drops, cutting off Wi-Fi on Ethernet-less laptops. **Mitigation:** Include `/etc/NetworkManager/` in dual backup archives, normalize permissions (`chmod 0600`, `chown root:root`) pre- and post-upgrade, and audit `nmcli` association in Phase 5.
9. **Hybrid Dual-GPU (Iris Plus + MX330) Wayland Regressions:** Linux 6.12 `simpledrm` and Optimus D3cold transitions can hang GDM3 at a black screen if secondary GPU handoff fails. **Mitigation:** Phase 5 DRM node audit (`/dev/dri/card0`, `/dev/dri/renderD128`), legacy `/etc/X11/xorg.conf.d/` sanitization, and embedding GPU black-screen rescue parameters (`nouveau.modeset=0`, `modprobe.blacklist=nouveau`) into the emergency rescue script.
10. **Package Cache Space Contention (`/var/cache/apt/archives`):** Downloading 1,500+ `.deb` archives consumes 3–6 GB simultaneously with new unpacked binaries, easily exceeding 10 GB peak transient usage. **Mitigation:** Increase root filesystem headroom requirement to $\ge 15\text{ GB}$, pass `-o APT::Keep-Downloaded-Packages="false"`, and execute intermediate `apt-get clean` immediately after Phase 3 minimal upgrade.
11. **The Dynamic Linker (`ld-linux`) Unpack Trap & Rescue Protocol:** If power is interrupted during `libc6` unpacking, internal chroot execution crashes due to glibc symbol mismatches. **Mitigation:** The emergency rescue protocol provides both offline host-level repair (`dpkg --root=/mnt --configure -a` and `apt-get -o RootDir=/mnt install -f`) and chroot runbooks including `/sys/firmware/efi/efivars` bind mounts, with an executable rescue script generated in persistent storage.
12. **NTFS-Safe Dual Backup Redundancy:** Copying raw POSIX directories via `cp -a` to NTFS storage (`/mnt/data`) loses permissions and corrupts symlinks. **Mitigation:** State snapshots (`/etc/apt/`, manifests, `/etc` and `/etc/NetworkManager` tarballs) are mirrored to persistent storage as compressed archives (`tar -czf`) at `/mnt/data/osm_backups/apt_pre_trixie_<timestamp>.tar.gz`.
13. **Python Runtime Decoupling:** Upgrading Python from 3.11 to 3.12+ breaks existing virtual environments (`.venv`). **Mitigation:** The core upgrade engine (`scripts/upgrade_debian_trixie.sh`) is a 100% zero-dependency POSIX Bash script, paired with `osm upgrade rebuild-venv` for post-upgrade environment regeneration.

---

## 2. Hardware & Storage Baseline

- **Model:** Lenovo IdeaPad 3 (81WD / 14IIL05 / 15IIL05) / Intel Core i5-1035G1 (Ice Lake)
- **Active Distribution:** Debian GNU/Linux 12.15 (Bookworm) $\rightarrow$ Debian 13 (Trixie)
- **Active Kernel:** Linux 6.1.0-52-amd64 $\rightarrow$ Linux 6.12+
- **Root Filesystem (`/`):** `/dev/nvme0n1p2` (ext4, ~228 GB, $\ge 15\text{ GB}$ free required)
- **Boot Directory (`/boot`):** Dedicated headroom $\ge 1.0\text{ GB}$ verified before execution
- **EFI Partition (`/boot/efi`):** `/dev/nvme0n1p1` (vfat, 96 MB, verified via `mountpoint -q /boot/efi`, $\ge 20\text{ MB}$ free)
- **Persistent Data (`/mnt/data`):** `/dev/nvme0n1p4` (NTFS, 244.1 GB, protected persistent storage verified via `mountpoint -q /mnt/data`)
- **Power Source:** AC Mains Adapter connected (`on_ac_power` true)
- **Memory & Swap:** Physical RAM + Swap $\ge 2.0\text{ GB}$ available headroom
- **Wi-Fi Controller:** Intel Ice Lake-LP PCH CNVi WiFi (Intel AC 9560 / `iwlwifi`, requiring `firmware-iwlwifi`)
- **Audio Controller:** Intel Ice Lake-LP Smart Sound Technology (requiring `firmware-sof-signed` and `alsa-ucm-conf`)
- **Graphics (GPU):** Intel Iris Plus Graphics G1 (`i915`) & NVIDIA GeForce MX330 (`nouveau` / `nvidia`)

---

## 3. Architecture & Execution Pipeline

The upgrade workflow consists of 6 sequential phases with strict transition boundaries:

```
[Phase 0: Pre-Flight Safety Gate]
       │ (Verify root, systemd-inhibit, AC power, RAM/swap, tmux, mountpoint checks, /boot >= 1GB, / >= 15GB, debconf)
       ▼
[Phase 1: Dual State Backup & NTFS-Safe Tarball Snapshot]
       │ (Save /var/backups/osm/ and tarball snapshot to /mnt/data/osm_backups/ + emergency_rescue.sh with GPU fallback)
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
[Phase 3: Minimal Safe Upgrade & Immediate Cache Clean] ──(Failure)──► [Emergency chroot / offline dpkg repair]
       │ (--without-new-pkgs, NEEDRESTART_MODE=a, debconf non-interactive, apt-get clean)
       ▼
[Phase 4: Full Distribution Upgrade & Core Firmware] ──(Failure)──► [Emergency chroot / offline dpkg repair]
       │ (full-upgrade, firmware-sof-signed, firmware-iwlwifi, firmware-misc-nonfree, alsa-ucm-conf, autoremove, clean)
       ▼
[Phase 5: Post-Upgrade Hardware, DRM, Network & Lockdown Audit]
         (Audit Wi-Fi/Audio SOF dmesg/DRM nodes/Lockdown/systemd, rebuild Python 3.12 .venv)
```

### Phase 0: Pre-Flight Safety Gate
- **Root Enforcement:** Require `EUID == 0` or execution via `sudo`.
- **Sleep & Lid-Switch Inhibition:** Self-wrap inside `systemd-inhibit --what=sleep:idle:shutdown:handle-lid-switch --why="Debian 13 Upgrade" --mode=block` if available and running as root.
- **Power Source Enforcement:** Assert AC power adapter is connected (`on_ac_power` or `/sys/class/power_supply/*/online`). Abort if running on battery power.
- **OOM Killer Isolation:** Adjust `/proc/$$/oom_score_adj` to `-1000` to prevent OOM termination of the upgrade process.
- **Memory & Swap Headroom:** Assert `MemAvailable + SwapTotal >= 2,097,152 KB` (2.0 GB) to guarantee headroom for parallel `zstd` initramfs compression.
- **Enclave & Multiplexer Protection:** Verify execution inside an active `tmux` (`$TMUX`), `screen` (`$STY`), or Linux virtual console (`/dev/tty[1-6]`). If unattached, automatically launch or prompt for `tmux`.
- **Physical Mountpoint Verification:**
  - Verify `/boot/efi` via `mountpoint -q /boot/efi` before checking ESP space ($\ge$ 20 MB).
  - Verify `/mnt/data` via `mountpoint -q /mnt/data` before scheduling secondary backup mirroring.
- **Storage Headroom:**
  - Root filesystem (`/`): minimum **15 GB** (15,728,640 KB) free.
  - Boot storage (`/boot`): minimum **1.0 GB** (1,048,576 KB) free for dual initramfs generation.
- **Network Probe:** Verify DNS resolution and HTTP reachability to `deb.debian.org`.
- **UEFI Secure Boot & DKMS Audit:** Inspect `mokutil --sb-state`. If enabled and DKMS packages are installed, verify/stage MOK key import (`mokutil --import`) and log instructions for post-reboot MOK enrollment.
- **NetworkManager Keyfile Permissions:** Normalize all `/etc/NetworkManager/system-connections/*` keyfiles to `0600` owned by `root:root`.
- **DPKG Consistency & Lock Free State:** Assert `dpkg --audit` returns 0 errors, check for held packages, and verify zero active `/var/lib/dpkg/lock*` or `/var/lib/apt/lists/lock` locks.
- **Debconf Pre-Seeding:**
  ```bash
  echo "grub2/force_efi_extra_removable boolean true" | debconf-set-selections
  echo "grub-efi-amd64 grub-efi/install_devices multiselect /dev/nvme0n1p1" | debconf-set-selections
  ```

### Phase 1: Dual State Backup & NTFS-Safe Tarball Snapshot
- **Primary Backup:** Create `/var/backups/osm/apt_pre_trixie_<timestamp>/` containing:
  - Recursive copy of `/etc/apt/` (sources, lists, keyrings).
  - Configuration archive: `etc_config_snapshot.tar.gz` (`/etc/fstab`, `/etc/default`, `/etc/network`, `/etc/NetworkManager`, `/etc/systemd`).
  - Package selections: `dpkg --get-selections > dpkg_selections.txt`.
  - Manual package markings: `apt-mark showmanual > apt_manual_pkgs.txt`.
  - Manifest metadata: `upgrade_manifest.json`.
- **Secondary NTFS Mirror:** If `/mnt/data` is mounted (`mountpoint -q /mnt/data`), package the entire backup directory into a single compressed tarball:
  ```bash
  tar -czf "/mnt/data/osm_backups/apt_pre_trixie_${timestamp}.tar.gz" -C "/var/backups/osm" "apt_pre_trixie_${timestamp}"
  ```
- **Rescue Script Generation:** Export `/mnt/data/osm_backups/emergency_rescue.sh` containing offline host repair, chroot with efivars, and GPU black-screen recovery boot parameters (`nouveau.modeset=0 modprobe.blacklist=nouveau`).

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
  ```bash
  dpkg --configure -a
  apt-get install -f -y
  ```
- **Emergency Rescue Protocol (Offline & Chroot):**
  If system crashes mid-unpack during `libc6` or bootloader installation:
  1. **Option A (External Host Repair - Survives Broken Dynamic Linker):**
     ```bash
     sudo mount /dev/nvme0n1p2 /mnt
     sudo mount /dev/nvme0n1p1 /mnt/boot/efi
     sudo dpkg --root=/mnt --configure -a
     sudo apt-get -o RootDir=/mnt update && sudo apt-get -o RootDir=/mnt install -f -y
     ```
  2. **Option B (Standard Chroot Recovery with EFI Variables):**
     ```bash
     sudo mount /dev/nvme0n1p2 /mnt
     sudo mount /dev/nvme0n1p1 /mnt/boot/efi
     for i in /dev /dev/pts /proc /sys /run; do sudo mount --bind $i /mnt$i; done
     sudo mount --bind /sys/firmware/efi/efivars /mnt/sys/firmware/efi/efivars
     sudo chroot /mnt
     dpkg --configure -a
     apt-get update && apt-get install -f -y
     update-initramfs -u -k all
     update-grub
     exit
     sudo reboot
     ```

### Phase 3: Minimal Safe Upgrade & Intermediate Cache Purge
- Environment variables:
  ```bash
  export DEBIAN_FRONTEND=noninteractive
  export DEBIAN_PRIORITY=critical
  export NEEDRESTART_MODE=a
  export NEEDRESTART_SUSPEND=1
  export UCF_FORCE_CONFFOLD=1
  ```
- Synchronize indexes: `apt-get update`.
- Execute staged minimal upgrade with streaming package download setting:
  ```bash
  apt-get upgrade --without-new-pkgs -y \
    -o Dpkg::Options::="--force-confdef" \
    -o Dpkg::Options::="--force-confold" \
    -o APT::Keep-Downloaded-Packages="false"
  ```
- **Intermediate Cache Purge:** Immediately reclaim package download space before Phase 4:
  ```bash
  apt-get clean
  ```

### Phase 4: Full Distribution Upgrade & Core Firmware
- Explicitly queue required firmware, sound architecture, and wireless packages:
  ```bash
  apt-get install --no-install-recommends -y \
    firmware-sof-signed \
    firmware-iwlwifi \
    firmware-misc-nonfree \
    alsa-ucm-conf \
    -o Dpkg::Options::="--force-confdef" \
    -o Dpkg::Options::="--force-confold" \
    -o APT::Keep-Downloaded-Packages="false"
  ```
- Execute complete distribution upgrade:
  ```bash
  apt-get full-upgrade -y \
    -o Dpkg::Options::="--force-confdef" \
    -o Dpkg::Options::="--force-confold" \
    -o APT::Keep-Downloaded-Packages="false"
  ```
- Clean unneeded orphaned packages: `apt-get autoremove --purge -y`.
- Clean download caches: `apt-get clean`.
- Re-enforce NetworkManager keyfile permissions (`chmod 0600 /etc/NetworkManager/system-connections/* 2>/dev/null || true`).

### Phase 5: Post-Upgrade Verification & Runtime Venv Rebuild
- **Hardware, DRM, Network & Systemd Audit:**
  - OS Release codename (`trixie`) & Kernel version (`uname -r` $\ge$ 6.12).
  - Intel AC 9560 / CNVi Wi-Fi (`iwlwifi` module and active wireless interface link state).
  - NetworkManager active profile association (`nmcli general status`).
  - Intel SST Audio SOF DSP driver binding (`dmesg | grep -iE 'sof-audio|soundwire|dsp'` verified with zero firmware errors).
  - Direct Rendering Manager (DRM) device node validation (`/dev/dri/card0` and `/dev/dri/renderD128` present).
  - UEFI Secure Boot & Kernel Lockdown status (`/sys/kernel/security/lockdown` mode logged, MOK enrollment prompt if DKMS built).
  - Zero degraded systemd services (`systemctl --failed`).
- **Python Virtualenv Rebuild:**
  - Subcommand `osm upgrade rebuild-venv` purges outdated Python 3.11 `.venv` folders and rebuilds clean environments with Python 3.12+.

---

## 4. Component Structure & CLI Specification

1. **Standalone Engine Script:** [`scripts/upgrade_debian_trixie.sh`](file:///home/rizz/dev/os-manager/scripts/upgrade_debian_trixie.sh)
   - Zero Python dependency; 100% Bash 4.4+ POSIX utilities.
   - Self-wraps under `systemd-inhibit`.
   - Flags: `--check`, `--dry-run`, `--backup-only`, `--apply`, `--verify`, `--allow-unattached`, `--non-interactive`.
2. **CLI Wrapper Router:** [`os_manager/commands/upgrade.py`](file:///home/rizz/dev/os-manager/os_manager/commands/upgrade.py)
   - Integrated into `osm upgrade` (`check`, `dry-run`, `start`, `verify`, `rebuild-venv`).
   - Automatically detects missing `tmux`, offers installation or bootstrap into `osm-trixie-upgrade` session.

---

## 5. Safety Guardrails & Zero-Data-Loss Invariants

1. **Persistent Partition Invariance:** `/dev/nvme0n1p4` (`/mnt/data`) is never formatted, resized, or unmounted.
2. **NTFS Data Safety:** All backups written to `/mnt/data` must be tarball-encapsulated (`.tar.gz`).
3. **Enclave & Sleep Invariance:** No upgrade execution without active `tmux`/`screen`/TTY3 protection and active `systemd-inhibit` sleep suppression unless explicitly overridden.
4. **Power Source Invariance:** No upgrade execution while running on battery power.
5. **Memory & OOM Invariance:** No execution under virtual memory deficit ($< 2.0\text{ GB}$); upgrade process protected via `oom_score_adj=-1000`.
6. **Firmware Retention Invariance:** `non-free-firmware` is mandatory across all generated deb822 stanzas; `firmware-sof-signed` is mandatory for Intel Ice Lake audio.
7. **Storage Headroom Invariance:** `/` must maintain $\ge 15.0\text{ GB}$ and `/boot` must maintain $\ge 1.0\text{ GB}$ free space before package operations begin.
