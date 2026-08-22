#!/usr/bin/env bash
# scripts/setup_desktop_env.sh - GNOME 48 Aesthetics, Ergonomics, Bookmarks, and Dconf
set -euo pipefail

BOOKMARKS_FILE="${HOME}/.config/gtk-3.0/bookmarks"
DCONF_PROFILE_PATH="${HOME}/.config/dconf/gnome-desktop.ini"

log_info()  { echo -e "\033[1;34m[INFO]\033[0m $*"; }
log_pass()  { echo -e "\033[1;32m[PASS]\033[0m $*"; }
log_warn()  { echo -e "\033[1;33m[WARN]\033[0m $*"; }
log_error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; }

add_bookmark() {
    local uri="${1:-file:///mnt/data}"
    local label="${2:-Data Store}"
    local file="${3:-${BOOKMARKS_FILE}}"

    mkdir -p "$(dirname "${file}")"
    touch "${file}"

    local entry="${uri} ${label}"
    if grep -qF "${uri}" "${file}"; then
        log_info "Bookmark for ${uri} already exists in ${file}."
    else
        echo "${entry}" >> "${file}"
        log_pass "Added bookmark: ${entry}"
    fi
}

apply_gsettings_tweaks() {
    log_info "Applying GNOME 48 typography, standard window controls, and ergonomics..."
    if ! command -v gsettings >/dev/null 2>&1; then
        log_warn "gsettings not available in current environment."
        return 0
    fi

    # Typography
    gsettings set org.gnome.desktop.interface font-name 'Inter 10.5' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface document-font-name 'Inter 11' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface monospace-font-name 'JetBrains Mono 10' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface font-antialiasing 'rgba' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface font-hinting 'slight' 2>/dev/null || true

    # Window Management & Ergonomics (Standard Right Controls)
    gsettings set org.gnome.desktop.wm.preferences button-layout 'appmenu:minimize,maximize,close' 2>/dev/null || true
    gsettings set org.gnome.mutter center-new-windows true 2>/dev/null || true
    gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark' 2>/dev/null || true
    gsettings set org.gnome.settings-daemon.plugins.color night-light-enabled true 2>/dev/null || true
    gsettings set org.gnome.desktop.wm.keybindings switch-applications "[]" 2>/dev/null || true
    gsettings set org.gnome.desktop.wm.keybindings switch-windows "['<Alt>Tab']" 2>/dev/null || true

    # Touchpad & Audio Over-Amplification
    gsettings set org.gnome.desktop.peripherals.touchpad tap-to-click true 2>/dev/null || true
    gsettings set org.gnome.desktop.peripherals.touchpad natural-scroll true 2>/dev/null || true
    gsettings set org.gnome.desktop.peripherals.touchpad disable-while-typing true 2>/dev/null || true
    gsettings set org.gnome.desktop.sound allow-volume-above-100-percent true 2>/dev/null || true

    # Nautilus Developer View
    gsettings set org.gnome.nautilus.preferences default-folder-viewer 'list-view' 2>/dev/null || true
    gsettings set org.gnome.nautilus.preferences date-time-format 'detailed' 2>/dev/null || true

    log_pass "Standard desktop gsettings configuration applied successfully."
}

apply_macos_gsettings_tweaks() {
    log_info "Applying GNOME 48 macOS Ver 3.0 visual preset (left traffic lights, typography, centered dock)..."
    if ! command -v gsettings >/dev/null 2>&1; then
        log_warn "gsettings not available in current environment."
        return 0
    fi

    # Typography & Subpixel Rendering
    gsettings set org.gnome.desktop.interface font-name 'Inter 10.5' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface document-font-name 'Inter 11' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface monospace-font-name 'JetBrains Mono 10' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface font-antialiasing 'rgba' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface font-hinting 'slight' 2>/dev/null || true

    # Window Management (macOS Traffic Light Buttons on Left)
    gsettings set org.gnome.desktop.wm.preferences button-layout 'close,minimize,maximize:' 2>/dev/null || true
    gsettings set org.gnome.mutter center-new-windows true 2>/dev/null || true

    # Dark Mode & Night Light
    gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark' 2>/dev/null || true
    gsettings set org.gnome.settings-daemon.plugins.color night-light-enabled true 2>/dev/null || true
    gsettings set org.gnome.desktop.wm.keybindings switch-applications "[]" 2>/dev/null || true
    gsettings set org.gnome.desktop.wm.keybindings switch-windows "['<Alt>Tab']" 2>/dev/null || true

    # Touchpad Natural Scrolling & Tap-to-Click
    gsettings set org.gnome.desktop.peripherals.touchpad tap-to-click true 2>/dev/null || true
    gsettings set org.gnome.desktop.peripherals.touchpad natural-scroll true 2>/dev/null || true
    gsettings set org.gnome.desktop.peripherals.touchpad disable-while-typing true 2>/dev/null || true
    gsettings set org.gnome.desktop.sound allow-volume-above-100-percent true 2>/dev/null || true

    # Nautilus Developer View
    gsettings set org.gnome.nautilus.preferences default-folder-viewer 'list-view' 2>/dev/null || true
    gsettings set org.gnome.nautilus.preferences date-time-format 'detailed' 2>/dev/null || true

    # Dash-to-Dock / Shell Preferences (Centered Bottom Dock, Autohide)
    gsettings set org.gnome.shell.extensions.dash-to-dock dock-position 'BOTTOM' 2>/dev/null || true
    gsettings set org.gnome.shell.extensions.dash-to-dock extend-height false 2>/dev/null || true
    gsettings set org.gnome.shell.extensions.dash-to-dock dash-max-icon-size 48 2>/dev/null || true
    gsettings set org.gnome.shell.extensions.dash-to-dock autohide true 2>/dev/null || true
    gsettings set org.gnome.shell.extensions.dash-to-dock dock-fixed false 2>/dev/null || true
    gsettings set org.gnome.shell.extensions.dash-to-dock intellihide true 2>/dev/null || true
    gsettings set org.gnome.shell.extensions.dash-to-dock custom-theme-shrink true 2>/dev/null || true
    gsettings set org.gnome.shell.extensions.dash-to-dock show-trash-icon false 2>/dev/null || true
    gsettings set org.gnome.shell.extensions.dash-to-dock show-mounts false 2>/dev/null || true

    log_pass "macOS Ver 3.0 desktop gsettings configuration applied successfully."
}

install_macos_theme_tools() {
    log_info "macOS Ver 3.0 Theme & Extensions Setup Guidance"
    echo "=================================================="
    echo "Recommended Theme Repositories & GNOME Extensions:"
    echo "1. WhiteSur GTK Theme: https://github.com/vinceliuice/WhiteSur-gtk-theme"
    echo "2. WhiteSur Icon Theme: https://github.com/vinceliuice/WhiteSur-icon-theme"
    echo "3. WhiteSur Cursor Theme: https://github.com/vinceliuice/WhiteSur-cursors"
    echo "4. GNOME Extensions: Dash to Dock, User Themes, Blur my Shell"
    echo "=================================================="
    echo "Quick Installation Commands:"
    echo "  git clone https://github.com/vinceliuice/WhiteSur-gtk-theme.git /tmp/WhiteSur-gtk-theme"
    echo "  bash /tmp/WhiteSur-gtk-theme/install.sh -c Dark -t all -N glassy -s 220"
    echo "  git clone https://github.com/vinceliuice/WhiteSur-icon-theme.git /tmp/WhiteSur-icon-theme"
    echo "  bash /tmp/WhiteSur-icon-theme/install.sh -a -t default"
    echo "=================================================="
    log_pass "macOS theme tools guidance displayed."
}

dump_dconf() {
    local target="${1:-${DCONF_PROFILE_PATH}}"
    mkdir -p "$(dirname "${target}")"
    if command -v dconf >/dev/null 2>&1; then
        dconf dump /org/gnome/ > "${target}"
        log_pass "Exported GNOME desktop dconf profile to: ${target}"
    else
        log_warn "dconf CLI utility not installed."
    fi
}

load_dconf() {
    local target="${1:-${DCONF_PROFILE_PATH}}"
    if [[ ! -f "${target}" ]]; then
        log_error "Dconf profile not found at: ${target}"
        return 1
    fi
    if command -v dconf >/dev/null 2>&1; then
        dconf load /org/gnome/ < "${target}"
        log_pass "Restored GNOME desktop dconf profile from: ${target}"
    else
        log_warn "dconf CLI utility not installed."
    fi
}

main() {
    local action="${1:---apply}"
    local preset="standard"

    case "${action}" in
        --apply)
            preset="${2:-standard}"
            add_bookmark "file:///mnt/data" "Data Store" "${BOOKMARKS_FILE}"
            if [[ "${preset}" == "macos" ]]; then
                apply_macos_gsettings_tweaks
            else
                apply_gsettings_tweaks
            fi
            ;;
        --preset)
            preset="${2:-standard}"
            add_bookmark "file:///mnt/data" "Data Store" "${BOOKMARKS_FILE}"
            if [[ "${preset}" == "macos" ]]; then
                apply_macos_gsettings_tweaks
            else
                apply_gsettings_tweaks
            fi
            ;;
        --install-macos-theme)
            install_macos_theme_tools
            ;;
        --bookmark)
            add_bookmark "${2:-file:///mnt/data}" "${3:-Data Store}" "${BOOKMARKS_FILE}"
            ;;
        --dconf-dump)
            dump_dconf "${2:-${DCONF_PROFILE_PATH}}"
            ;;
        --dconf-load)
            load_dconf "${2:-${DCONF_PROFILE_PATH}}"
            ;;
        *)
            echo "Usage: $(basename "$0") [--apply [standard|macos]|--preset [standard|macos]|--install-macos-theme|--bookmark|--dconf-dump|--dconf-load]"
            exit 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
