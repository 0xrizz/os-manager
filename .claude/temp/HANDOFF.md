# HANDOFF: Legacy Runtime Cleanup & Mise Global Tool Migration

**Date**: 2026-08-31
**Originating Session**: User Mode OS Optimization (Completed Phase 1 Memory, Phase 2 Mise Full Latest, Phase 3 Wayland & GPU Power, Phase 4 GNOME 48 Tiling, and Post-Phase 2 Legacy Auditing)
**Target Next Session**: Execute global CLI package migrations, update autostart desktop entry, and remove physical legacy runtime directories (`~/.nvm`, `~/.bun`)
**Execution Method**: `executing-plans` / direct operations

---

## 1. Current Status & System Baseline

- **All 4 Adaptation Phases Complete & Verified (`[PASSED]` 100%)**:
  - `Phase 1 (Memory & Sysctl)`: 100% zRAM (~7.33 GB, ZSTD, Priority 100) + `/etc/sysctl.d/99-osm-memory.conf` + `earlyoom` active.
  - `Phase 2 (Polyglot Runtimes)`: Standalone `mise` SSOT (`~/.local/bin/mise`), full latest runtimes (Node.js v26.8.1, Python 3.14.7, Bun 1.4.0, UV 0.12.7), system Python isolated.
  - `Phase 3 (Wayland & GPU Power)`: GDM3 Wayland default, NVIDIA RTD3 dynamic PM (`/etc/modprobe.d/99-nvidia-pm.conf`, `NVreg_DynamicPowerManagement=0x02`, `NVreg_UseKernelSuspendNotifiers=1`), initramfs synced, `prime-run` wrapper operational.
  - `Phase 4 (GNOME 48 Tiling)`: Tiling Shell active, declarative GSettings window & workspace keybindings, `<Super>Return` terminal launcher.
- **Audited Legacy Inventory**:
  - `~/.nvm` (1.1 GB): Holds `v24.19.0` and `v26.7.0`. Active global CLIs identified: `9router`, `@fission-ai/openspec`, `wrangler`.
  - `~/.bun` (78 MB): Legacy standalone binaries only (`bun`, `bunx`). Zero global modules.
  - `~/.config/autostart/9router.desktop`: Contains hardcoded path to `~/.nvm/versions/node/v26.7.0/bin/node`.

---

## 2. Active TODO List (Next Directives)

1. **Step 1 - Migrate Global Node Packages to Mise**:
   - Install required global CLIs under Mise Node environment:
     ```bash
     ~/.local/share/mise/shims/npm install -g 9router @fission-ai/openspec wrangler
     ```
   - Verify shim resolution:
     ```bash
     command -v 9router && command -v openspec && command -v wrangler
     ```

2. **Step 2 - Update 9router Autostart Desktop Entry**:
   - Update `~/.config/autostart/9router.desktop` Exec path to use Mise shim:
     ```bash
     sed -i 's|Exec=.*9router.*|Exec=/home/rizz/.local/share/mise/shims/9router --tray --skip-update|' ~/.config/autostart/9router.desktop
     ```

3. **Step 3 - Evict Physical Legacy Directories (Reclaim ~1.2 GB)**:
   - Remove legacy NVM and Bun folders:
     ```bash
     rm -rf ~/.nvm ~/.bun
     ```

4. **Step 4 - Run Full Post-Cleanup Verification Probe**:
   - Execute verification probe:
     ```bash
     /home/rizz/dev/os-manager/temp/user-mode/scripts/verify_polyglot_runtimes.sh
     ```

5. **Step 5 - Mandatory Cleanup (Rule 2)**:
   - Once all steps above are complete and verified, truncate `.claude/temp/HANDOFF.md` to 0 bytes.

---

## 3. Suggested Skills for Next Session

- `verification-before-completion`
- `executing-plans`

---

## 4. Technical Constraints & Invariants

- **User Mode Workspace Immutability**: All repository source code in `os-manager/` remains strictly READ-ONLY.
- **Zero-Stall Privileged Execution**: Always use `./scripts/sudo_exec.sh` if elevated privileges are needed.
- **Debian System Python Isolation**: Do not use `pip install` or modify `/usr/bin/python3` directly. All user packages must route through `mise` or `uv`.
