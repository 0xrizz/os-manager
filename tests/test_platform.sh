#!/usr/bin/env bash
# tests/test_platform.sh - Unit test suite for universal platform abstraction library
# shellcheck disable=SC1090,SC2030,SC2031
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PLATFORM_LIB="${WORKSPACE_ROOT}/scripts/lib/platform.sh"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

assert_equals() {
    local test_name="$1"
    local expected="$2"
    local actual="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ "${expected}" = "${actual}" ]; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (expected: '${expected}', got: '${actual}')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running Platform Abstraction Unit Tests"
echo "=================================================="

# 1. Test library existence and syntax (Assertion 1)
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -f "${PLATFORM_LIB}" ]; then
    echo "  [PASS] platform.sh exists"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] platform.sh missing at ${PLATFORM_LIB}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Helper to run platform_detect with mock uname, proc_version, and os-release
test_mock_os_release() {
    local test_id="$1"
    local mock_content="$2"
    local expected_family="$3"
    local expected_pkg="$4"
    local mock_release_file="/tmp/mock_os_release_${test_id}"
    local mock_version_file="/tmp/mock_proc_ver_${test_id}"

    echo "${mock_content}" > "${mock_release_file}"
    echo "Linux version 6.1.0-generic (gcc version 12.2.0)" > "${mock_version_file}"

    local result
    result="$(
        export OSM_UNAME_S="Linux"
        export OSM_PROC_VERSION_FILE="${mock_version_file}"
        export OS_RELEASE_FILE="${mock_release_file}"
        if [ -f "${PLATFORM_LIB}" ]; then
            source "${PLATFORM_LIB}"
            platform_detect
            echo "${OSM_DISTRO_FAMILY}:${OSM_PKG_MANAGER}"
        else
            echo "missing:missing"
        fi
    )"
    rm -f "${mock_release_file}" "${mock_version_file}"

    local actual_family="${result%%:*}"
    local actual_pkg="${result##*:}"

    assert_equals "${test_id} Family Detection" "${expected_family}" "${actual_family}"
    assert_equals "${test_id} Package Manager Mapping" "${expected_pkg}" "${actual_pkg}"
}

# 2. Test Debian 13 (Assertions 2 & 3)
test_mock_os_release "Debian-13" \
'PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
NAME="Debian GNU/Linux"
VERSION_ID="13"
VERSION="13 (trixie)"
ID=debian
HOME_URL="https://www.debian.org/"' \
"debian" "apt"

# 3. Test Ubuntu 24.04 (Assertions 4 & 5)
test_mock_os_release "Ubuntu-24.04" \
'PRETTY_NAME="Ubuntu 24.04 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
ID=ubuntu
ID_LIKE=debian' \
"debian" "apt"

# 4. Test Arch Linux (Assertions 6 & 7)
test_mock_os_release "Arch-Linux" \
'NAME="Arch Linux"
PRETTY_NAME="Arch Linux"
ID=arch
BUILD_ID=rolling' \
"arch" "pacman"

# 5. Test Fedora 40 (Assertions 8 & 9)
test_mock_os_release "Fedora-40" \
'NAME="Fedora Linux"
VERSION="40 (Workstation Edition)"
ID=fedora
VERSION_ID="40"
PRETTY_NAME="Fedora Linux 40"' \
"fedora" "dnf"

# 6. Test openSUSE Leap 15.6 (Assertions 10 & 11)
test_mock_os_release "openSUSE-Leap" \
'NAME="openSUSE Leap"
VERSION="15.6"
ID="opensuse-leap"
ID_LIKE="suse opensuse"
PRETTY_NAME="openSUSE Leap 15.6"' \
"suse" "zypper"

# 7. Test Alpine Linux 3.20 (Assertions 12 & 13)
test_mock_os_release "Alpine-Linux" \
'NAME="Alpine Linux"
ID=alpine
VERSION_ID=3.20.0
PRETTY_NAME="Alpine Linux v3.20"' \
"alpine" "apk"

# 8. Test WSL2 Linux Platform Detection (Assertion 14)
test_mock_wsl() {
    local mock_release_file="/tmp/mock_wsl_release"
    local mock_version_file="/tmp/mock_wsl_version"

    echo 'ID=debian
VERSION_ID="13"
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"' > "${mock_release_file}"
    echo "Linux version 6.6.36.3-microsoft-standard-WSL2 (oe-user@oe-host)" > "${mock_version_file}"

    local result
    result="$(
        export OSM_UNAME_S="Linux"
        export OSM_PROC_VERSION_FILE="${mock_version_file}"
        export OS_RELEASE_FILE="${mock_release_file}"
        if [ -f "${PLATFORM_LIB}" ]; then
            source "${PLATFORM_LIB}"
            platform_detect
            echo "${OSM_PLATFORM}:${OSM_NOTIFY_ENGINE}"
        else
            echo "missing:missing"
        fi
    )"
    rm -f "${mock_release_file}" "${mock_version_file}"

    assert_equals "WSL2-Debian Platform & Notification" "wsl:winrt" "${result}"
}
test_mock_wsl

# 9. Test macOS Darwin Platform Detection (Assertion 15)
test_mock_macos() {
    local result
    result="$(
        export OSM_UNAME_S="Darwin"
        export OSM_PROC_VERSION_FILE="/tmp/nonexistent_proc_ver"
        export OS_RELEASE_FILE="/tmp/nonexistent_os_release"
        if [ -f "${PLATFORM_LIB}" ]; then
            source "${PLATFORM_LIB}"
            platform_detect
            echo "${OSM_PLATFORM}:${OSM_DISTRO_FAMILY}:${OSM_PKG_MANAGER}:${OSM_SERVICE_MANAGER}:${OSM_NOTIFY_ENGINE}"
        else
            echo "missing:missing:missing:missing:missing"
        fi
    )"

    assert_equals "macOS-Darwin Platform & Toolchain" "macos:darwin:brew:launchd:osascript" "${result}"
}
test_mock_macos

# 10. Test Path Defaults Initialization (Assertion 16)
test_path_defaults() {
    local result
    result="$(
        unset OSM_ROOT OSM_BACKUP_DIR OSM_LOG_DIR OSM_RUN_DIR
        export HOME="/tmp/mock_user_home"
        if [ -f "${PLATFORM_LIB}" ]; then
            source "${PLATFORM_LIB}"
            platform_init_paths
            echo "${OSM_ROOT}:${OSM_BACKUP_DIR}:${OSM_LOG_DIR}:${OSM_RUN_DIR}"
        else
            echo "missing"
        fi
    )"
    local expected="/tmp/mock_user_home/.os-manager:/tmp/mock_user_home/.local/share/os-manager/backups:/tmp/mock_user_home/.local/state/os-manager/logs:/tmp/os-manager-${UID}"
    assert_equals "Path Defaults Resolution" "${expected}" "${result}"
}
test_path_defaults

# 11. Test Path Sanitization (Assertion 17)
TOTAL_TESTS=$((TOTAL_TESTS + 1))
HARDCODED_MATCHES="$(grep -rnI --exclude-dir=__pycache__ "/home/rizz" "${WORKSPACE_ROOT}/scripts" "${WORKSPACE_ROOT}/systemd" "${WORKSPACE_ROOT}/.claude/commands" "${WORKSPACE_ROOT}/.claude/rules" "${WORKSPACE_ROOT}/.claude/skills" || true)"
if [ -z "${HARDCODED_MATCHES}" ]; then
    echo "  [PASS] Path Sanitization (Zero hardcoded /home/rizz references)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Hardcoded user home found in active files:"
    echo "${HARDCODED_MATCHES}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 12. Test Dotfile Templates Existence (Assertion 18)
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -f "${WORKSPACE_ROOT}/backups/dotfiles/.bashrc.example" ] && \
   [ -f "${WORKSPACE_ROOT}/backups/dotfiles/.tmux.conf.example" ] && \
   [ -f "${WORKSPACE_ROOT}/backups/dotfiles/.gitconfig.example" ]; then
    echo "  [PASS] Dotfiles .example templates exist"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Missing .example dotfile templates"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 13. Test Dotfile Sanitization (Assertion 19)
TOTAL_TESTS=$((TOTAL_TESTS + 1))
DOTFILES_MATCHES="$(grep -rnI "/home/rizz" "${WORKSPACE_ROOT}/backups/dotfiles" || true)"
if [ -z "${DOTFILES_MATCHES}" ]; then
    echo "  [PASS] Dotfiles templates sanitized (Zero personal paths)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Personal paths found in dotfiles templates:"
    echo "${DOTFILES_MATCHES}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo "=================================================="
echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
