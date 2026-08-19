#!/usr/bin/env bash
# tests/test_distro.sh - Unit test suite for cross-distribution discovery library
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DISTRO_LIB="${WORKSPACE_ROOT}/scripts/lib/distro.sh"

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
echo "Running Cross-Distribution Engine Unit Tests"
echo "=================================================="

# 1. Test library existence and syntax
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -f "${DISTRO_LIB}" ]; then
    echo "  [PASS] distro.sh exists"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] distro.sh missing at ${DISTRO_LIB}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Helper to run detect_distro with a mock /etc/os-release file
test_mock_os_release() {
    local test_id="$1"
    local mock_content="$2"
    local expected_family="$3"
    local expected_pkg="$4"
    local mock_file="/tmp/mock_os_release_${test_id}"

    echo "${mock_content}" > "${mock_file}"

    # Execute in a subshell sourcing distro.sh with overridden OS_RELEASE_FILE
    local result
    result="$(
        export OSM_UNAME_S="Linux"
        export OS_RELEASE_FILE="${mock_file}"
        # shellcheck disable=SC1090
        source "${DISTRO_LIB}"
        detect_distro
        echo "${OS_DISTRO_FAMILY}:${OS_PKG_MANAGER}"
    )"
    rm -f "${mock_file}"

    local actual_family="${result%%:*}"
    local actual_pkg="${result##*:}"

    assert_equals "${test_id} Family Detection" "${expected_family}" "${actual_family}"
    assert_equals "${test_id} Package Manager Mapping" "${expected_pkg}" "${actual_pkg}"
}

# 2. Test Debian 13
test_mock_os_release "Debian-13" \
'PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
NAME="Debian GNU/Linux"
VERSION_ID="13"
VERSION="13 (trixie)"
ID=debian
HOME_URL="https://www.debian.org/"' \
"debian" "apt"

# 3. Test Ubuntu 24.04
test_mock_os_release "Ubuntu-24.04" \
'PRETTY_NAME="Ubuntu 24.04 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
ID=ubuntu
ID_LIKE=debian' \
"debian" "apt"

# 4. Test Arch Linux
test_mock_os_release "Arch-Linux" \
'NAME="Arch Linux"
PRETTY_NAME="Arch Linux"
ID=arch
BUILD_ID=rolling' \
"arch" "pacman"

# 5. Test Fedora 40
test_mock_os_release "Fedora-40" \
'NAME="Fedora Linux"
VERSION="40 (Workstation Edition)"
ID=fedora
VERSION_ID="40"
PRETTY_NAME="Fedora Linux 40 (Workstation Edition)"' \
"fedora" "dnf"

# 6. Test openSUSE Tumbleweed
test_mock_os_release "openSUSE" \
'NAME="openSUSE Tumbleweed"
ID="opensuse-tumbleweed"
ID_LIKE="opensuse suse"
PRETTY_NAME="openSUSE Tumbleweed"' \
"suse" "zypper"

# 7. Test Alpine Linux
test_mock_os_release "Alpine-3.20" \
'NAME="Alpine Linux"
ID=alpine
VERSION_ID=3.20.0
PRETTY_NAME="Alpine Linux v3.20"' \
"alpine" "apk"

echo "=================================================="
echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
