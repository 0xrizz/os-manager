#!/usr/bin/env bash
# scripts/lib/distro.sh - Backwards-compatible shim delegating to platform.sh
# shellcheck disable=SC2153
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/platform.sh"

# Map new OSM_* variables to legacy OS_* variables for complete compatibility
OS_DISTRO_ID="${OSM_DISTRO_ID}"
OS_DISTRO_FAMILY="${OSM_DISTRO_FAMILY}"
OS_DISTRO_VERSION="${OSM_DISTRO_VERSION}"
OS_DISTRO_NAME="${OSM_DISTRO_NAME}"
OS_PKG_MANAGER="${OSM_PKG_MANAGER}"
OS_SERVICE_MANAGER="${OSM_SERVICE_MANAGER}"

export OS_DISTRO_ID OS_DISTRO_FAMILY OS_DISTRO_VERSION OS_DISTRO_NAME OS_PKG_MANAGER OS_SERVICE_MANAGER

detect_distro() {
    platform_detect
    OS_DISTRO_ID="${OSM_DISTRO_ID}"
    OS_DISTRO_FAMILY="${OSM_DISTRO_FAMILY}"
    OS_DISTRO_VERSION="${OSM_DISTRO_VERSION}"
    OS_DISTRO_NAME="${OSM_DISTRO_NAME}"
    OS_PKG_MANAGER="${OSM_PKG_MANAGER}"
    OS_SERVICE_MANAGER="${OSM_SERVICE_MANAGER}"
    export OS_DISTRO_ID OS_DISTRO_FAMILY OS_DISTRO_VERSION OS_DISTRO_NAME OS_PKG_MANAGER OS_SERVICE_MANAGER
}

pkg_update() { platform_pkg_cmd update "$@"; }
pkg_upgrade() { platform_pkg_cmd upgrade "$@"; }
pkg_clean() { platform_pkg_cmd clean "$@"; }
pkg_install() { platform_pkg_cmd install "$@"; }
