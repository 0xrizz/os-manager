# Report: macOS Ver 3.0 Visual Preset Implementation for Debian 13 Desktop

## 1. Executive Summary

This report documents the implementation of the **macOS Ver 3.0 Visual Preset** within the Debian 13 (Trixie) Desktop Customization Engine in `os-manager`. The enhancement provides a refined macOS-like workstation aesthetic (traffic light window controls on the left, centered bottom dock, Inter & JetBrains Mono typography with subpixel rendering, dark mode, adaptive night light, and theme installer tools) while maintaining strict idempotency, root/user separation, and WSL2/headless resilience.

---

## 2. Implemented Components

### 2.1 Shell Script Extension (`scripts/setup_desktop_env.sh`)
* **`apply_macos_gsettings_tweaks()`**: Configures:
  * Window button layout: `org.gnome.desktop.wm.preferences button-layout 'close,minimize,maximize:'` (macOS traffic lights on left).
  * Centered new windows: `org.gnome.mutter center-new-windows true`.
  * Typography: Inter 10.5 (UI), Inter 11 (Documents), JetBrains Mono 10 (Monospace), with `rgba` subpixel antialiasing and `slight` hinting.
  * Dark mode & Night Light: `prefer-dark` color scheme and adaptive blue light filter.
  * Touchpad & Audio: Natural scrolling, tap-to-click, disable-while-typing, audio over-amplification above 100%.
  * Dash-to-Dock preferences: Bottom position, centered (`extend-height false`), 48px icon size, intelligent autohide, clean icons without trash/mounts.
* **`install_macos_theme_tools()`**: Guidance and helper commands for WhiteSur GTK theme, WhiteSur icon theme, WhiteSur cursors, and GNOME shell extensions.
* **CLI Switch Support**: Added `--preset [standard|macos]`, `--apply [standard|macos]`, and `--install-macos-theme`.

### 2.2 Python CLI & Engine (`os_manager/commands/tune.py`)
* **`apply_desktop_gsettings(preset: str = "standard") -> dict[str, bool]`**: Dynamically applies `'close,minimize,maximize:'` and Dash-to-Dock schemas when `preset="macos"`, maintaining standard right-hand buttons `'appmenu:minimize,maximize,close'` when `preset="standard"`.
* **CLI Subparser**: Added `--preset` (`choices=["standard", "macos"]`, default `"standard"`) to `osm tune desktop`.

### 2.3 Unit & CLI Testing
* **`tests/test_desktop_customization.py`**:
  * Added `test_apply_desktop_gsettings_macos_preset()` verifying that `'close,minimize,maximize:'` and `dash-to-dock` settings are invoked.
  * Updated `test_apply_desktop_gsettings()` to verify standard button layout.
* **`tests/test_cli.py`**:
  * Added `test_tune_desktop_preset_macos()` verifying CLI dispatch of `osm tune desktop --preset macos`.

### 2.4 Documentation (`docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md`)
* Added Section 4.4 detailing the macOS Ver 3.0 preset features and visual layout.
* Updated Section 6 (CLI Catalog) and Section 7 (Bash Execution) with macOS preset commands.
* Updated architectural Mermaid diagram.

---

## 3. Constraint & SRE Invariant Verification

| Invariant | Status | Verification Detail |
|---|---|---|
| **INV-01 (Zero Data Loss)** | **VERIFIED** | `/mnt/data` persistent storage is untouched; GTK bookmark points cleanly to `file:///mnt/data Data Store`. |
| **INV-02 (Strict Idempotency)** | **VERIFIED** | All GSettings tweaks and bookmark additions are safe to execute repeatedly without duplicating configurations. |
| **INV-03 (Root vs User Boundary)** | **VERIFIED** | Desktop aesthetic tweaks execute strictly within user-space without sudo escalation. |
| **INV-05 (WSL2 & Headless Resilience)** | **VERIFIED** | Checks `command -v gsettings`, redirects stderr with `2>/dev/null || true`, and handles mock test suites cleanly. |

---

## 4. Test Verification Results

### Unit Test Execution:
```
Ran 24 tests in 0.216s
OK
```

### Master Regression Harness (`bash tests/test_harness.sh`):
```
Summary: 68/68 passed
Exit code: 0
```

---

## 5. Commit Information

* **Commit Message**: `feat(desktop): add macOS Ver 3.0 aesthetic preset to desktop customization suite`
* **Files Modified**:
  * `scripts/setup_desktop_env.sh`
  * `os_manager/commands/tune.py`
  * `tests/test_desktop_customization.py`
  * `tests/test_cli.py`
  * `docs/DEBIAN_13_CUSTOMIZATION_GUIDE.md`
  * `.agents/macos-preset-report.md`
