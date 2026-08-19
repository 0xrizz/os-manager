#!/usr/bin/env bash
# scripts/lib/platform.sh - Universal Platform & Operating System Abstraction Engine
set -euo pipefail

# Exported Global Platform Descriptors
OSM_PLATFORM=""
OSM_DISTRO_ID=""
OSM_DISTRO_FAMILY=""
OSM_DISTRO_VERSION=""
OSM_DISTRO_NAME=""
OSM_PKG_MANAGER=""
OSM_SERVICE_MANAGER=""
OSM_NOTIFY_ENGINE=""

# Path Initializer Defaults
platform_init_paths() {
    export OSM_ROOT="${OSM_ROOT:-${HOME}/.os-manager}"
    export OSM_BACKUP_DIR="${OSM_BACKUP_DIR:-${HOME}/.local/share/os-manager/backups}"
    export OSM_LOG_DIR="${OSM_LOG_DIR:-${HOME}/.local/state/os-manager/logs}"
    export OSM_RUN_DIR="${OSM_RUN_DIR:-/tmp/os-manager-${UID}}"
    export OSM_DEV_ROOT="${OSM_DEV_ROOT:-${HOME}/dev}"
}

platform_detect() {
    local uname_s="${OSM_UNAME_S:-$(uname -s 2>/dev/null || echo "Unknown")}"
    local proc_ver_file="${OSM_PROC_VERSION_FILE:-/proc/version}"
    local os_release_file="${OS_RELEASE_FILE:-/etc/os-release}"

    case "${uname_s}" in
        Darwin)
            OSM_PLATFORM="macos"
            OSM_DISTRO_ID="darwin"
            OSM_DISTRO_FAMILY="darwin"
            OSM_DISTRO_NAME="macOS"
            OSM_DISTRO_VERSION="$(sw_vers -productVersion 2>/dev/null || echo "unknown")"
            OSM_PKG_MANAGER="brew"
            OSM_SERVICE_MANAGER="launchd"
            OSM_NOTIFY_ENGINE="osascript"
            ;;
        Linux)
            # Check WSL2 kernel signature
            local is_wsl=false
            if [ -f "${proc_ver_file}" ]; then
                if grep -qi "microsoft" "${proc_ver_file}" 2>/dev/null; then
                    is_wsl=true
                fi
            fi

            if [ "${is_wsl}" = true ]; then
                OSM_PLATFORM="wsl"
                OSM_NOTIFY_ENGINE="winrt"
            else
                OSM_PLATFORM="linux"
                OSM_NOTIFY_ENGINE="notify-send"
            fi

            OSM_SERVICE_MANAGER="systemd"

            # Parse Linux Distribution
            if [ -f "${os_release_file}" ]; then
                local id="" id_like="" version_id="" pretty_name=""
                while IFS='=' read -r key val || [ -n "${key}" ]; do
                    key="$(echo "${key}" | tr -d '[:space:]')"
                    val="$(echo "${val}" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")"
                    case "${key}" in
                        ID) id="${val}" ;;
                        ID_LIKE) id_like="${val}" ;;
                        VERSION_ID) version_id="${val}" ;;
                        PRETTY_NAME) pretty_name="${val}" ;;
                    esac
                done < "${os_release_file}"

                OSM_DISTRO_ID="${id:-unknown}"
                OSM_DISTRO_NAME="${pretty_name:-Linux}"
                OSM_DISTRO_VERSION="${version_id:-rolling}"

                case "${OSM_DISTRO_ID}" in
                    debian|ubuntu|pop|linuxmint|kali|elementary|raspbian)
                        OSM_DISTRO_FAMILY="debian"
                        OSM_PKG_MANAGER="apt"
                        ;;
                    arch|endeavouros|manjaro|artix|garuda)
                        OSM_DISTRO_FAMILY="arch"
                        OSM_PKG_MANAGER="pacman"
                        ;;
                    fedora|rhel|centos|rocky|alma|nobara)
                        OSM_DISTRO_FAMILY="fedora"
                        OSM_PKG_MANAGER="dnf"
                        ;;
                    opensuse*|suse|sles)
                        OSM_DISTRO_FAMILY="suse"
                        OSM_PKG_MANAGER="zypper"
                        ;;
                    alpine)
                        OSM_DISTRO_FAMILY="alpine"
                        OSM_PKG_MANAGER="apk"
                        ;;
                    *)
                        if [[ "${id_like}" =~ (debian|ubuntu) ]]; then
                            OSM_DISTRO_FAMILY="debian"
                            OSM_PKG_MANAGER="apt"
                        elif [[ "${id_like}" =~ (arch) ]]; then
                            OSM_DISTRO_FAMILY="arch"
                            OSM_PKG_MANAGER="pacman"
                        elif [[ "${id_like}" =~ (fedora|rhel|centos) ]]; then
                            OSM_DISTRO_FAMILY="fedora"
                            OSM_PKG_MANAGER="dnf"
                        elif [[ "${id_like}" =~ (suse|opensuse) ]]; then
                            OSM_DISTRO_FAMILY="suse"
                            OSM_PKG_MANAGER="zypper"
                        else
                            OSM_DISTRO_FAMILY="generic"
                            OSM_PKG_MANAGER="unknown"
                        fi
                        ;;
                esac
            else
                if command -v apt-get &>/dev/null; then
                    OSM_DISTRO_ID="debian"
                    OSM_DISTRO_FAMILY="debian"
                    OSM_PKG_MANAGER="apt"
                elif command -v pacman &>/dev/null; then
                    OSM_DISTRO_ID="arch"
                    OSM_DISTRO_FAMILY="arch"
                    OSM_PKG_MANAGER="pacman"
                elif command -v dnf &>/dev/null; then
                    OSM_DISTRO_ID="fedora"
                    OSM_DISTRO_FAMILY="fedora"
                    OSM_PKG_MANAGER="dnf"
                elif command -v zypper &>/dev/null; then
                    OSM_DISTRO_ID="suse"
                    OSM_DISTRO_FAMILY="suse"
                    OSM_PKG_MANAGER="zypper"
                elif command -v apk &>/dev/null; then
                    OSM_DISTRO_ID="alpine"
                    OSM_DISTRO_FAMILY="alpine"
                    OSM_PKG_MANAGER="apk"
                else
                    OSM_DISTRO_ID="generic"
                    OSM_DISTRO_FAMILY="generic"
                    OSM_PKG_MANAGER="unknown"
                fi
                OSM_DISTRO_NAME="Generic Linux"
                OSM_DISTRO_VERSION="unknown"
            fi
            ;;
        *)
            OSM_PLATFORM="unknown"
            OSM_DISTRO_ID="unknown"
            OSM_DISTRO_FAMILY="unknown"
            OSM_DISTRO_NAME="Unknown OS"
            OSM_DISTRO_VERSION="unknown"
            OSM_PKG_MANAGER="unknown"
            OSM_SERVICE_MANAGER="none"
            OSM_NOTIFY_ENGINE="none"
            ;;
    esac

    export OSM_PLATFORM OSM_DISTRO_ID OSM_DISTRO_FAMILY OSM_DISTRO_VERSION \
           OSM_DISTRO_NAME OSM_PKG_MANAGER OSM_SERVICE_MANAGER OSM_NOTIFY_ENGINE
}

# Package Operation Dispatchers
platform_pkg_cmd() {
    local action="$1"
    shift || true

    case "${action}" in
        update)
            case "${OSM_PKG_MANAGER}" in
                apt) sudo apt update "$@" ;;
                pacman) sudo pacman -Sy "$@" ;;
                dnf)
                    local rc=0
                    sudo dnf check-update "$@" || rc=$?
                    if [ "$rc" -eq 100 ] || [ "$rc" -eq 0 ]; then return 0; else return "$rc"; fi
                    ;;
                zypper) sudo zypper refresh "$@" ;;
                apk) sudo apk update "$@" ;;
                brew) brew update "$@" ;;
                *) echo "[platform.sh] Unsupported package manager for update: ${OSM_PKG_MANAGER}" >&2; return 1 ;;
            esac
            ;;
        upgrade)
            case "${OSM_PKG_MANAGER}" in
                apt) sudo apt upgrade -y "$@" ;;
                pacman) sudo pacman -Syu --noconfirm "$@" ;;
                dnf) sudo dnf upgrade -y "$@" ;;
                zypper) sudo zypper update -y "$@" ;;
                apk) sudo apk upgrade "$@" ;;
                brew) brew upgrade "$@" ;;
                *) echo "[platform.sh] Unsupported package manager for upgrade: ${OSM_PKG_MANAGER}" >&2; return 1 ;;
            esac
            ;;
        clean)
            case "${OSM_PKG_MANAGER}" in
                apt) sudo apt autoremove -y && sudo apt clean ;;
                pacman)
                    sudo pacman -Sc --noconfirm
                    if command -v paccache &>/dev/null; then
                        sudo paccache -r || true
                    fi
                    ;;
                dnf) sudo dnf autoremove -y && sudo dnf clean all ;;
                zypper) sudo zypper clean --all ;;
                apk) [ -d /var/cache/apk ] && sudo rm -rf /var/cache/apk/* ;;
                brew) brew cleanup -s ;;
                *) echo "[platform.sh] Unsupported package manager for clean: ${OSM_PKG_MANAGER}" >&2; return 1 ;;
            esac
            ;;
        install)
            if [ $# -eq 0 ]; then
                echo "Usage: platform_pkg_cmd install <package_name...>" >&2
                return 1
            fi
            case "${OSM_PKG_MANAGER}" in
                apt) sudo apt install -y "$@" ;;
                pacman) sudo pacman -S --noconfirm --needed "$@" ;;
                dnf) sudo dnf install -y "$@" ;;
                zypper) sudo zypper install -y --no-confirm "$@" ;;
                apk) sudo apk add "$@" ;;
                brew) brew install "$@" ;;
                *) echo "[platform.sh] Unsupported package manager for install: ${OSM_PKG_MANAGER}" >&2; return 1 ;;
            esac
            ;;
        *)
            echo "Usage: platform_pkg_cmd {update|upgrade|clean|install} [args...]" >&2
            return 1
            ;;
    esac
}

# Auto-initialize paths and detect platform on source
platform_init_paths
platform_detect
