# Debian 13 (Trixie) Desktop & Hardware Customization Design Specification

**Status:** APPROVED  
**Date:** 2026-08-22  
**Author:** Lead Systems Tooling Architect & Desktop Experience Engineer  
**Target Environment:** Bare-Metal Debian GNU/Linux 13 (Trixie), Linux Kernel 6.12+, GNOME 48 (Wayland), Lenovo IdeaPad 3 (81WD) with Intel Ice Lake + NVIDIA MX330  
**Target Plan:** [`docs/superpowers/plans/2026-08-22-debian-13-desktop-and-hardware-customization.md`](file:///home/rizz/dev/os-manager/docs/superpowers/plans/2026-08-22-debian-13-desktop-and-hardware-customization.md)

---

## 1. Executive Summary & Objective

Following the successful in-place distribution upgrade to Debian 13 (Trixie) and Linux Kernel 6.12, the objective of this specification is to establish an automated, idempotent, and test-driven customization suite for:
1. **Hardware Power & Thermal Management:** Automated Lenovo IdeaPad battery conservation mode (60% charging threshold via ACPI kernel module `ideapad_laptop`) and hardware video decoding acceleration (VA-API on Intel Iris Plus Graphics G1).
2. **GNOME 48 Desktop Aesthetics, Ergonomics & Developer Workflow:** Native typography integration (Inter & JetBrains Mono), subpixel font rendering, window management ergonomics (minimize/maximize, centered placement, window-based Alt+Tab), full dark theme & night light schedule, touchpad gestures/tap-to-click tuning, audio over-amplification, Nautilus list-view & terminal integration, Extension Manager deployment, and declarative `dconf` desktop state backup/restore.
3. **Modern Terminal & Developer Experience (DX):** Starship cross-shell prompt, fuzzy file/history search (`fzf`), smart directory navigation (`zoxide`), syntax-highlighted paging (`bat`), and modern file listings (`eza`).
4. **CLI Control Plane Integration:** Consolidated management under `osm tune` (`battery`, `vaapi`, `desktop`, `terminal`, `all`) with full JSON telemetry and master harness validation.

---

## 2. Architectural Invariants & Safety Guardrails

| Invariant ID | Name | Architectural Rule |
| :--- | :--- | :--- |
| **INV-01** | **Zero Data Loss on `/mnt/data`** | All operations strictly treat `/dev/nvme0n1p4` (`/mnt/data`) as persistent read/write storage. No partition, format, or mount disruption is permitted. |
| **INV-02** | **Strict Idempotency** | Every script subroutine (`tune_hardware.sh`, `setup_desktop_env.sh`, `setup_terminal_env.sh`) must be safe to run repeatedly without creating duplicate entries in `~/.bashrc`, `~/.config/gtk-3.0/bookmarks`, or system configurations. |
| **INV-03** | **Root vs User Boundary Separation** | System package installations (`apt-get`) and sysfs writes (`/sys/bus/platform/...`) require root/sudo privileges. All user-space dotfiles and desktop configurations (`~/.config/starship.toml`, `~/.bashrc`, `bookmarks`, `gsettings`, `dconf`) must be executed under the active user's `$HOME` with non-root ownership. |
| **INV-04** | **Hybrid GPU & Wayland Decoupling** | All display rendering and VA-API hardware decoders prioritize Intel Iris Plus Graphics (`i915` / `/dev/dri/card0` / `/dev/dri/renderD128`) on Wayland to maximize battery longevity and eliminate Wayland compositor lockups. |
| **INV-05** | **Offline/Fallback Resilience** | Python CLI subcommands must provide graceful fallbacks (e.g. headless/no D-Bus detection for `gsettings`, `uv` fallback when `python3-venv` is missing, warnings on non-Lenovo hardware). |

---

## 3. Subsystem Architecture & Technical Specifications

```mermaid
flowchart TD
    CLI["osm tune CLI Router (Python 3.13)"] --> SUB1["Hardware Tuning Subsystem (scripts/tune_hardware.sh)"]
    CLI --> SUB2["Desktop Aesthetics & Ergonomics Subsystem (scripts/setup_desktop_env.sh)"]
    CLI --> SUB3["Terminal DX Subsystem (scripts/setup_terminal_env.sh)"]

    SUB1 --> ACPI["Lenovo Conservation Mode (/sys/.../conservation_mode)"]
    SUB1 --> VAAPI["Intel VA-API Driver (intel-media-va-driver-non-free)"]

    SUB2 --> FONTS["Typography (Inter & JetBrains Mono) + Subpixel Rendering"]
    SUB2 --> THEME["Dark Mode + Accent + Night Light + Window Ergonomics"]
    SUB2 --> TOUCHPAD["Touchpad (Tap-to-click, Natural Scroll) + Audio Boost"]
    SUB2 --> NAUTILUS["Nautilus List View + Bookmarks + Terminal Menu"]
    SUB2 --> EXT["GNOME Extensions + Declarative dconf Backup/Restore"]

    SUB3 --> STARSHIP["Starship Prompt (~/.config/starship.toml)"]
    SUB3 --> TOOLS["Modern CLI Suite (fzf, zoxide, bat, eza)"]
    SUB3 --> BASHRC["Shell Hooks & Aliases (~/.bashrc)"]
```

---

### 3.1 Subsystem 1: Lenovo Hardware Power & VA-API Video Acceleration

#### 1. Lenovo Battery Conservation Mode:
* **Sysfs Path:** `/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode`
* **Driver:** Kernel module `ideapad_laptop`
* **Behavior:**
  * Writing `1` stops charging when the battery capacity reaches ~60%, preventing battery degradation during continuous AC wall power operation.
  * Writing `0` allows normal 100% full charging.
* **CLI Interface:** `osm tune battery [status|on|off]`

#### 2. Intel VA-API Hardware Video Decoding:
* **Target Hardware:** Intel Core i5-1035G1 (Intel Iris Plus Graphics G1 / Ice Lake)
* **Required Packages:** `intel-media-va-driver-non-free`, `vainfo`, `i965-va-driver-shaders`
* **Verification Command:** `vainfo` inspecting `VAProfileH264Main`, `VAProfileHEVCMain`, `VAProfileVP9Profile0` for `VAEntrypointVLD`.
* **CLI Interface:** `osm tune vaapi [status|install]`

---

### 3.2 Subsystem 2: GNOME 48 Desktop Aesthetics, Ergonomics & Developer Workflow

#### 1. Modern Typography & Subpixel Font Rendering:
* **System Packages:** `fonts-inter`, `fonts-jetbrains-mono`
* **Applied GSettings Configurations:**
  * UI Interface Font: `org.gnome.desktop.interface font-name 'Inter 10.5'`
  * Document Font: `org.gnome.desktop.interface document-font-name 'Inter 11'`
  * Monospace / Code Font: `org.gnome.desktop.interface monospace-font-name 'JetBrains Mono 10'`
  * Text Sharpness (1080p LCD): `org.gnome.desktop.interface font-antialiasing 'rgba'`
  * Subpixel Hinting: `org.gnome.desktop.interface font-hinting 'slight'`

#### 2. Window Management, Dark Theme & Ergonomics:
* **Window Controls:** Enable minimize, maximize, and close buttons on all windows:
  * `org.gnome.desktop.wm.preferences button-layout 'appmenu:minimize,maximize,close'`
* **Window Placement:** Automatically center newly spawned application windows:
  * `org.gnome.mutter center-new-windows true`
* **Dark Mode & Eye Comfort:**
  * Global Dark Theme: `org.gnome.desktop.interface color-scheme 'prefer-dark'`
  * Legacy GTK Theme: `org.gnome.desktop.interface gtk-theme 'Adwaita-dark'`
  * Automatic Night Light (Sunset to Sunrise): `org.gnome.settings-daemon.plugins.color night-light-enabled true`
* **Developer Window Switching:** Switch directly between distinct windows instead of grouped applications:
  * `org.gnome.desktop.wm.keybindings switch-applications "[]"`
  * `org.gnome.desktop.wm.keybindings switch-windows "['<Alt>Tab']"`

#### 3. Lenovo Laptop Touchpad & Audio Amplification Tuning:
* **Touchpad Peripherals (`gsettings`):**
  * Tap-to-Click (1 finger = left click, 2 fingers = right click): `org.gnome.desktop.peripherals.touchpad tap-to-click true`
  * Two-Finger Natural Scrolling: `org.gnome.desktop.peripherals.touchpad natural-scroll true`
  * Palm / Typing Rejection: `org.gnome.desktop.peripherals.touchpad disable-while-typing true`
* **Audio Over-Amplification:**
  * Boost speaker output volume beyond 100% (up to 150%) for clear video calls and media: `org.gnome.desktop.sound allow-volume-above-100-percent true`

#### 4. Nautilus Developer Ergonomics & Data Store Bookmark:
* **Data Store Sidebar Bookmark:**
  * Target File: `${HOME}/.config/gtk-3.0/bookmarks`
  * Format: `file:///mnt/data Data Store`
  * Verification: Idempotent lookup using `grep -qF "file:///mnt/data"` before appending.
* **Developer View Settings:**
  * Default Folder Viewer: `org.gnome.nautilus.preferences default-folder-viewer 'list-view'`
  * Detailed Timestamp Format: `org.gnome.nautilus.preferences date-time-format 'detailed'`
* **Terminal Context Integration:**
  * System Package: `nautilus-extension-gnome-terminal` (enables right-click *"Open in Terminal"*).

#### 5. GNOME Extensions Ecosystem & Declarative Dconf State Management:
* **System Packages:** `gnome-shell-extension-manager`, `gnome-tweaks`, `gnome-shell-extension-appindicator`, `dconf-cli`
* **Curated Top Extensions:**
  * *AppIndicator Support* (Tray icons in top panel for developer tools).
  * *Blur my Shell* (Frosted-glass translucency on Wayland top panel & overview).
  * *Just Perfection* (Fine-grained GNOME 48 panel and animation customization).
  * *Clipboard Indicator* (Top-bar persistent clipboard history manager).
  * *Vitals* (Real-time CPU, RAM, temperature, and fan speed telemetry in top bar).
* **Declarative Desktop Profiles (`dconf` Export/Import):**
  * Target File: `${HOME}/.config/dconf/gnome-desktop.ini`
  * `osm tune desktop backup [filepath]` $\rightarrow$ Exports current `/org/gnome/` settings via `dconf dump`.
  * `osm tune desktop restore [filepath]` $\rightarrow$ Restores `/org/gnome/` settings via `dconf load`.

---

### 3.3 Subsystem 3: Modern Terminal & Developer Experience (DX)

#### 1. Starship Prompt Engine:
* **Configuration:** `${HOME}/.config/starship.toml`
* **Prompt Format:** Directory truncation (`3`), Git branch & status styling, Python virtual environment detection, and execution status symbol (`❯`).
* **Installation:** Idempotent check for `starship` binary; downloads official prebuilt binary if uninstalled.

#### 2. Modern CLI Utilities:
* **`fzf`:** Interactive fuzzy-finder for reverse command search (`Ctrl+R`) and file completion (`Ctrl+T`).
* **`zoxide`:** Smart directory jumper with frecency algorithm (`alias cd="z"`).
* **`bat` (`batcat`):** Cat clone with syntax highlighting and Git integration (`alias cat="bat --paging=never"`).
* **`eza`:** Modern replacement for `ls` with icons, file metadata, and directory-first sorting (`alias ls="eza --icons"`).

#### 3. Shell Hook Idempotency:
* Configuration block encapsulated within a distinctive marker:
  ```bash
  # --- os-manager Terminal Power-Up Hooks ---
  ```

---

## 4. CLI Control Plane Interface Specification

The `osm tune` command group provides unified access to all customization features:

```bash
# Audit all hardware power, media, and environment tuning
osm tune audit

# Manage Lenovo battery conservation mode
osm tune battery status
osm tune battery on
osm tune battery off

# Inspect and install VA-API video decoding acceleration
osm tune vaapi status
osm tune vaapi install

# Configure GNOME typography, dark theme, ergonomics, touchpad, bookmarks, and extensions
osm tune desktop
osm tune desktop apply
osm tune desktop audit
osm tune desktop backup [path/to/backup.ini]
osm tune desktop restore [path/to/backup.ini]

# Configure Starship prompt, fzf, zoxide, and modern CLI tools
osm tune terminal

# Run all customization subroutines end-to-end
osm tune all
```

---

## 5. Verification & Testing Matrix

| Test Suite | Scope | Target Assertions |
| :--- | :--- | :--- |
| `tests/test_tune_hardware.py` | Python unit tests for battery sysfs reading/writing, VA-API detection, and CLI argument parsing. | • Mock sysfs read `1` $\rightarrow$ `enabled`<br/>• Mock sysfs read `0` $\rightarrow$ `disabled`<br/>• Non-existent path $\rightarrow$ `unsupported`<br/>• `set_battery_conservation_mode` invokes `tee`<br/>• `audit_vaapi_acceleration` parses vainfo output |
| `tests/test_desktop_customization.py` | Python unit tests for GTK 3 bookmarks, GSettings schema configuration, and Dconf backup/restore. | • Fresh bookmark creation writes `file:///mnt/data Data Store`<br/>• Subsequent calls do not duplicate entries<br/>• Respects custom bookmark path overrides<br/>• `apply_desktop_gsettings` executes expected `gsettings set` calls<br/>• `dconf_dump_desktop` and `dconf_load_desktop` export/import cleanly |
| `tests/test_terminal_customization.py` | Python unit tests for Starship configuration generation and `.bashrc` alias injection. | • TOML configuration contains directory, git, and python modules<br/>• `.bashrc` alias injection includes marker and hooks<br/>• Re-running is strictly idempotent |
| `tests/test_harness.sh` | Master regression test suite integration. | • All new unit suites pass with exit code 0<br/>• Zero hardcoded path leaks<br/>• 100% clean harness execution |

---

## 6. Execution & Rollout Plan

1. **Task 1:** Lenovo Hardware Power Tuning & VA-API Video Acceleration Engine ([`scripts/tune_hardware.sh`](file:///home/rizz/dev/os-manager/scripts/tune_hardware.sh)).
2. **Task 2:** GNOME 48 Desktop Aesthetics, Ergonomics, Nautilus Data Store Bookmarking & Dconf State ([`scripts/setup_desktop_env.sh`](file:///home/rizz/dev/os-manager/scripts/setup_desktop_env.sh)).
3. **Task 3:** Modern Terminal & Developer Experience Suite ([`scripts/setup_terminal_env.sh`](file:///home/rizz/dev/os-manager/scripts/setup_terminal_env.sh)).
4. **Task 4:** CLI Router Integration (`osm tune`), Master Harness Registration, and Documentation Guide ([`docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md`](file:///home/rizz/dev/os-manager/docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md)).
