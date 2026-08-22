#!/usr/bin/env bash
# scripts/setup_desktop_env.sh - GNOME 48 Aesthetics, Ergonomics, Bookmarks, and Dconf
set -euo pipefail

BOOKMARKS_FILE="${HOME}/.config/gtk-3.0/bookmarks"
DCONF_PROFILE_PATH="${HOME}/.config/dconf/gnome-desktop.ini"
BACKUP_DIR="${HOME}/.config/osm/backups"

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
    local variant="${1:-full}"
    log_info "Applying GNOME 48 macOS Ver 3.0 visual preset (variant: ${variant}, left traffic lights, typography, centered dock)..."
    if ! command -v gsettings >/dev/null 2>&1; then
        log_warn "gsettings not available in current environment."
        return 0
    fi

    # Window Management (macOS Traffic Light Buttons on Left)
    gsettings set org.gnome.desktop.wm.preferences button-layout 'close,minimize,maximize:' 2>/dev/null || true
    gsettings set org.gnome.mutter center-new-windows true 2>/dev/null || true

    # Themes
    gsettings set org.gnome.desktop.interface gtk-theme 'WhiteSur-Dark' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface icon-theme 'WhiteSur-dark' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface cursor-theme 'WhiteSur-cursors' 2>/dev/null || true
    gsettings set org.gnome.shell.extensions.user-theme name 'WhiteSur-Dark' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface color-scheme 'prefer-dark' 2>/dev/null || true

    # Typography & Subpixel Rendering
    gsettings set org.gnome.desktop.interface font-name 'SF Pro Text 10.5' 2>/dev/null || gsettings set org.gnome.desktop.interface font-name 'Inter 10.5' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface document-font-name 'SF Pro Text 11' 2>/dev/null || gsettings set org.gnome.desktop.interface document-font-name 'Inter 11' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface monospace-font-name 'SF Mono 10' 2>/dev/null || gsettings set org.gnome.desktop.interface monospace-font-name 'JetBrains Mono 10' 2>/dev/null || true
    gsettings set org.gnome.desktop.wm.preferences titlebar-font 'SF Pro Display Bold 10.5' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface font-antialiasing 'rgba' 2>/dev/null || true
    gsettings set org.gnome.desktop.interface font-hinting 'slight' 2>/dev/null || true

    # Dark Mode & Night Light
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

    # Extensions for full mode
    if [[ "${variant}" == "full" || "${variant}" == "macos-full" ]]; then
        gsettings set org.gnome.shell.extensions.blur-my-shell.panel blur true 2>/dev/null || true
        gsettings set org.gnome.shell.extensions.blur-my-shell.dash-to-dock blur true 2>/dev/null || true
        gsettings set org.gnome.shell.extensions.magic-lamp animation-time 350 2>/dev/null || true
    fi

    log_pass "macOS (${variant}) desktop gsettings configuration applied successfully."
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

create_snapshot() {
    local bdir="${1:-${BACKUP_DIR}}"
    mkdir -p "${bdir}"
    local timestamp
    timestamp="$(date +'%Y%m%d-%H%M%S')"
    local snap_file="${bdir}/desktop-${timestamp}.dconf"

    if command -v dconf >/dev/null 2>&1; then
        if dconf dump /org/gnome/ > "${snap_file}"; then
            log_pass "Created desktop settings snapshot at: ${snap_file}"
            return 0
        else
            log_warn "Failed to create dconf snapshot."
            return 1
        fi
    else
        log_warn "dconf CLI utility not installed."
        return 1
    fi
}

restore_snapshot() {
    local snap_file="${1:-}"
    if [[ -z "${snap_file}" ]]; then
        local latest
        latest="$(find "${BACKUP_DIR}" -maxdepth 1 -name "desktop-*.dconf" 2>/dev/null | sort -r | head -n 1 || true)"
        if [[ -z "${latest}" || ! -f "${latest}" ]]; then
            log_error "No desktop snapshot found to restore in ${BACKUP_DIR}."
            return 1
        fi
        snap_file="${latest}"
    fi

    if [[ ! -f "${snap_file}" ]]; then
        log_error "Dconf snapshot file not found: ${snap_file}"
        return 1
    fi

    if command -v dconf >/dev/null 2>&1; then
        if dconf load /org/gnome/ < "${snap_file}"; then
            log_pass "Restored desktop settings from: ${snap_file}"
            return 0
        else
            log_error "Failed to restore dconf settings from: ${snap_file}"
            return 1
        fi
    else
        log_warn "dconf CLI utility not installed."
        return 1
    fi
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

show_help() {
    cat << 'EOF'
Usage: setup_desktop_env.sh [OPTIONS]

GNOME 48 Aesthetics, Ergonomics, Bookmarks, and macOS Desktop Setup

Options:
  --preset [standard|macos|macos-full|macos-core]
                            Apply desktop ergonomics and aesthetic preset (default: standard)
  --apply [standard|macos|macos-full|macos-core]
                            Alias for --preset
  --backup [file]           Create timestamped snapshot of GNOME dconf settings
                            (saved to ~/.config/osm/backups/ by default)
  --restore [file]          Restore GNOME dconf settings from snapshot or file
                            (restores latest snapshot if file omitted)
  --install-macos-theme     Display guidance and upstream repository setup commands
                            for WhiteSur GTK, icons, cursors, and extensions
  --bookmark [uri] [label]  Add persistent bookmark to GTK/Nautilus
  --dconf-dump [file]       Dump GNOME desktop dconf profile to specific file
  --dconf-load [file]       Load GNOME desktop dconf profile from specific file
  -h, --help                Show this help message and exit

Examples:
  ./scripts/setup_desktop_env.sh --preset macos-full
  ./scripts/setup_desktop_env.sh --backup
  ./scripts/setup_desktop_env.sh --restore
EOF
}

main() {
    local action="${1:---apply}"
    local preset="standard"

    case "${action}" in
        -h|--help|help)
            show_help
            exit 0
            ;;
        --backup)
            if [[ -n "${2:-}" ]]; then
                dump_dconf "$2"
            else
                create_snapshot
            fi
            ;;
        --restore)
            if [[ -n "${2:-}" ]]; then
                restore_snapshot "$2"
            else
                restore_snapshot
            fi
            ;;
        --apply|--preset)
            preset="${2:-standard}"
            # Safety net: automated snapshot before changes
            create_snapshot >/dev/null 2>&1 || true
            add_bookmark "file:///mnt/data" "Data Store" "${BOOKMARKS_FILE}"
            case "${preset}" in
                macos-full|macos)
                    apply_macos_gsettings_tweaks "full"
                    ;;
                macos-core)
                    apply_macos_gsettings_tweaks "core"
                    ;;
                standard|*)
                    apply_gsettings_tweaks
                    ;;
            esac
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
            log_error "Unknown option: ${action}"
            echo "Usage: $(basename "$0") [--preset standard|macos|macos-full|macos-core|--backup|--restore|--install-macos-theme|--bookmark|--dconf-dump|--dconf-load|--help]"
            exit 1
            ;;
    esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
