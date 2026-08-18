#!/usr/bin/env bash
# scripts/lib/distro.sh - Cross-Distribution Detection & Package Abstraction Library
set -euo pipefail

OS_DISTRO_ID=""
OS_DISTRO_FAMILY=""
OS_DISTRO_VERSION=""
OS_DISTRO_NAME=""
OS_PKG_MANAGER=""
OS_SERVICE_MANAGER="systemd"

detect_distro() {
    local os_release="${OS_RELEASE_FILE:-/etc/os-release}"

    if [ -f "${os_release}" ]; then
        local id="" id_like="" version_id="" pretty_name=""

        # Read properties safely without unrestricted execution
        while IFS='=' read -r key val || [ -n "${key}" ]; do
            # Trim whitespace and quotes
            key="$(echo "${key}" | tr -d '[:space:]')"
            val="$(echo "${val}" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")"
            case "${key}" in
                ID) id="${val}" ;;
                ID_LIKE) id_like="${val}" ;;
                VERSION_ID) version_id="${val}" ;;
                PRETTY_NAME) pretty_name="${val}" ;;
            esac
        done < "${os_release}"

        OS_DISTRO_ID="${id:-unknown}"
        OS_DISTRO_NAME="${pretty_name:-Linux}"
        OS_DISTRO_VERSION="${version_id:-rolling}"

        case "${OS_DISTRO_ID}" in
            debian|ubuntu|pop|linuxmint|kali|elementary|raspbian)
                OS_DISTRO_FAMILY="debian"
                OS_PKG_MANAGER="apt"
                ;;
            arch|endeavouros|manjaro|artix|garuda)
                OS_DISTRO_FAMILY="arch"
                OS_PKG_MANAGER="pacman"
                ;;
            fedora|rhel|centos|rocky|alma|nobara)
                OS_DISTRO_FAMILY="fedora"
                OS_PKG_MANAGER="dnf"
                ;;
            opensuse*|suse|sles)
                OS_DISTRO_FAMILY="suse"
                OS_PKG_MANAGER="zypper"
                ;;
            alpine)
                OS_DISTRO_FAMILY="alpine"
                OS_PKG_MANAGER="apk"
                ;;
            *)
                # Check ID_LIKE fallback matches
                if [[ "${id_like}" =~ (debian|ubuntu) ]]; then
                    OS_DISTRO_FAMILY="debian"
                    OS_PKG_MANAGER="apt"
                elif [[ "${id_like}" =~ (arch) ]]; then
                    OS_DISTRO_FAMILY="arch"
                    OS_PKG_MANAGER="pacman"
                elif [[ "${id_like}" =~ (fedora|rhel|centos) ]]; then
                    OS_DISTRO_FAMILY="fedora"
                    OS_PKG_MANAGER="dnf"
                elif [[ "${id_like}" =~ (suse|opensuse) ]]; then
                    OS_DISTRO_FAMILY="suse"
                    OS_PKG_MANAGER="zypper"
                else
                    OS_DISTRO_FAMILY="generic"
                    OS_PKG_MANAGER="unknown"
                fi
                ;;
        esac
    else
        # Fallback binary discovery heuristic
        if command -v apt-get &>/dev/null; then
            OS_DISTRO_ID="debian"
            OS_DISTRO_FAMILY="debian"
            OS_PKG_MANAGER="apt"
        elif command -v pacman &>/dev/null; then
            OS_DISTRO_ID="arch"
            OS_DISTRO_FAMILY="arch"
            OS_PKG_MANAGER="pacman"
        elif command -v dnf &>/dev/null; then
            OS_DISTRO_ID="fedora"
            OS_DISTRO_FAMILY="fedora"
            OS_PKG_MANAGER="dnf"
        elif command -v zypper &>/dev/null; then
            OS_DISTRO_ID="suse"
            OS_DISTRO_FAMILY="suse"
            OS_PKG_MANAGER="zypper"
        elif command -v apk &>/dev/null; then
            OS_DISTRO_ID="alpine"
            OS_DISTRO_FAMILY="alpine"
            OS_PKG_MANAGER="apk"
        else
            OS_DISTRO_ID="generic"
            OS_DISTRO_FAMILY="generic"
            OS_PKG_MANAGER="unknown"
        fi
        OS_DISTRO_NAME="Generic Linux"
        OS_DISTRO_VERSION="unknown"
    fi

    export OS_DISTRO_ID OS_DISTRO_FAMILY OS_DISTRO_VERSION OS_DISTRO_NAME OS_PKG_MANAGER OS_SERVICE_MANAGER
}

pkg_update() {
    case "${OS_DISTRO_FAMILY}" in
        debian)
            sudo apt update "$@"
            ;;
        arch)
            sudo pacman -Sy "$@"
            ;;
        fedora)
            local rc=0
            sudo dnf check-update "$@" || rc=$?
            if [ "$rc" -eq 100 ] || [ "$rc" -eq 0 ]; then
                return 0
            else
                return "$rc"
            fi
            ;;
        suse)
            sudo zypper refresh "$@"
            ;;
        alpine)
            sudo apk update "$@"
            ;;
        *)
            echo "[distro.sh] Warning: Unsupported package family '${OS_DISTRO_FAMILY}'; skipping pkg_update." >&2
            return 0
            ;;
    esac
}

pkg_upgrade() {
    case "${OS_DISTRO_FAMILY}" in
        debian)
            sudo apt upgrade -y "$@"
            ;;
        arch)
            sudo pacman -Syu --noconfirm "$@"
            ;;
        fedora)
            sudo dnf upgrade -y "$@"
            ;;
        suse)
            sudo zypper update -y "$@"
            ;;
        alpine)
            sudo apk upgrade "$@"
            ;;
        *)
            echo "[distro.sh] Warning: Unsupported package family '${OS_DISTRO_FAMILY}'; skipping pkg_upgrade." >&2
            return 0
            ;;
    esac
}

pkg_clean() {
    case "${OS_DISTRO_FAMILY}" in
        debian)
            sudo apt autoremove -y
            sudo apt clean
            ;;
        arch)
            sudo pacman -Sc --noconfirm
            if command -v paccache &>/dev/null; then
                sudo paccache -r || true
            fi
            ;;
        fedora)
            sudo dnf autoremove -y
            sudo dnf clean all
            ;;
        suse)
            sudo zypper clean --all
            ;;
        alpine)
            if [ -d /var/cache/apk ]; then
                sudo rm -rf /var/cache/apk/*
            fi
            ;;
        *)
            echo "[distro.sh] Warning: Unsupported package family '${OS_DISTRO_FAMILY}'; skipping pkg_clean." >&2
            return 0
            ;;
    esac
}

pkg_install() {
    if [ $# -eq 0 ]; then
        echo "Usage: pkg_install <package_name...>" >&2
        return 1
    fi

    case "${OS_DISTRO_FAMILY}" in
        debian)
            sudo apt install -y "$@"
            ;;
        arch)
            sudo pacman -S --noconfirm --needed "$@"
            ;;
        fedora)
            sudo dnf install -y "$@"
            ;;
        suse)
            sudo zypper install -y --no-confirm "$@"
            ;;
        alpine)
            sudo apk add "$@"
            ;;
        *)
            echo "[distro.sh] Error: Cannot install packages on unsupported family '${OS_DISTRO_FAMILY}'" >&2
            return 1
            ;;
    esac
}

# Auto-detect on source
detect_distro
