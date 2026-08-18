# Cross-Distribution Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a zero-dependency Linux distribution discovery and package manager abstraction library (`scripts/lib/distro.sh`), generalize Tier 3 package purge guardrails across all major package managers (APT, Pacman, DNF, Zypper, APK) in `scripts/hooks/pre_tool_guard.sh`, and refactor maintenance scripts (`clean_system.sh`, `update_runtimes.sh`, `sys_diag.sh`) for cross-distro portability.

**Architecture:** A lightweight POSIX shell library (`scripts/lib/distro.sh`) parses `/etc/os-release` (with fallback to binary discovery) to classify the running environment into standard families (`debian`, `arch`, `fedora`, `suse`, `alpine`, `generic`) and exports normalized variables (`OS_DISTRO_ID`, `OS_DISTRO_FAMILY`, `OS_PKG_MANAGER`, `OS_DISTRO_NAME`, `OS_DISTRO_VERSION`). Normalized wrapper functions (`pkg_update`, `pkg_upgrade`, `pkg_clean`, `pkg_install`) provide unified, non-interactive execution across all package managers. PreToolUse lifecycle guardrails are generalized to block catastrophic mass package removal across all ecosystems.

**Tech Stack:** Bash 5.2+, POSIX `/etc/os-release`, APT, Pacman, DNF, Zypper, APK, `jq`, `shellcheck`.

**Spec:** `docs/superpowers/specs/2026-08-19-cross-distribution-engine-design.md`

## Global Constraints

- **Strict Error Handling**: All shell scripts must declare `set -euo pipefail` and maintain Unix LF line endings.
- **Zero External Dependencies**: Distribution discovery must rely exclusively on `/etc/os-release` parsing and standard shell builtins without requiring Python, Perl, or compiled helpers.
- **Deterministic Guardrails**: `scripts/hooks/pre_tool_guard.sh` must deterministically block mass package purges with Exit Code 2 across APT, Pacman, DNF, Zypper, and APK.
- **Safe Fallback Execution**: Maintenance scripts must degrade gracefully when run on unsupported or generic distributions without unhandled shell crashes.

---

### Task 1: Create Unit Test Suite for Cross-Distribution Discovery

**Files:**
- Create: `tests/test_distro.sh`

**Interfaces:**
- Consumes: `scripts/lib/distro.sh` (`detect_distro`, `pkg_update`, `pkg_upgrade`, `pkg_clean`, `pkg_install`)
- Produces: Automated test suite validating OS family resolution, package manager mapping, and mocked dry-run package operations.

- [ ] **Step 1: Write the failing unit test suite with mock OS fixtures**

```bash
cat <<'EOF' > tests/test_distro.sh
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
EOF
chmod +x tests/test_distro.sh
```

- [ ] **Step 2: Run test to verify it fails**

Run: `tests/test_distro.sh`
Expected: FAIL with `distro.sh missing` error.

- [ ] **Step 3: Commit unit test suite**

```bash
git add tests/test_distro.sh
git commit -m "test(distro): add cross-distribution discovery unit test suite"
```

---

### Task 2: Implement Distribution Discovery and Package Abstraction Library

**Files:**
- Create: `scripts/lib/distro.sh`
- Test: `tests/test_distro.sh`

**Interfaces:**
- Consumes: `/etc/os-release` (or `$OS_RELEASE_FILE`)
- Produces: `detect_distro()`, `pkg_update()`, `pkg_upgrade()`, `pkg_clean()`, `pkg_install()`

- [ ] **Step 1: Write the implementation for `scripts/lib/distro.sh`**

```bash
mkdir -p scripts/lib
cat <<'EOF' > scripts/lib/distro.sh
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
            sudo dnf check-update "$@" || [ $? -eq 100 ]
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
EOF
chmod +x scripts/lib/distro.sh
```

- [ ] **Step 2: Run test to verify it passes**

Run: `shellcheck scripts/lib/distro.sh && tests/test_distro.sh`
Expected: PASS (All 13 assertions pass).

- [ ] **Step 3: Commit implementation**

```bash
git add scripts/lib/distro.sh
git commit -m "feat(distro): implement distribution detection and package manager abstraction library"
```

---

### Task 3: Generalize Tier 3 Safety Invariant Guardrails

**Files:**
- Modify: `scripts/hooks/pre_tool_guard.sh`
- Test: `tests/test_harness.sh`

**Interfaces:**
- Consumes: Tool execution JSON on `stdin`
- Produces: Exit Code 2 on destructive package manager purges (`apt`, `pacman`, `dnf`, `zypper`, `apk`).

- [ ] **Step 1: Write the failing test assertions for generalized package blocks in `tests/test_harness.sh`**

Add tests for Pacman, DNF, Zypper, and APK wildcard purge attempts to `tests/test_harness.sh`:
```bash
# In tests/test_harness.sh:
PAYLOAD_TIER3_PACMAN='{"tool_name":"Bash","tool_input":{"command":"pacman -Rcs *"}}'
PAYLOAD_TIER3_DNF='{"tool_name":"Bash","tool_input":{"command":"dnf remove --all"}}'
PAYLOAD_TIER3_ZYPPER='{"tool_name":"Bash","tool_input":{"command":"zypper remove *"}}'
PAYLOAD_TIER3_APK='{"tool_name":"Bash","tool_input":{"command":"apk del *"}}'
```

- [ ] **Step 2: Update `scripts/hooks/pre_tool_guard.sh` with Generalized Regex Filters**

Verify that `scripts/hooks/pre_tool_guard.sh` contains the complete multi-distro regex pattern:
```bash
    # Invariant Block: Indiscriminate Package Purging (Generalized across all distros)
    if echo "${CMD}" | grep -qE '\b(apt|apt-get|pacman|dnf|zypper|apk)\s+(purge|remove|del|-Rcs)\s+(\*|all|--all)\b' || \
       echo "${CMD}" | grep -qE '\b(apt|apt-get|dpkg)\s+(--purge\s+)?(purge|remove)\s+-[a-zA-Z0-9]*\*\b' || \
       echo "${CMD}" | grep -qE '\bpacman\s+-[Rksu]+\s+.*(\b|\s)(base|systemd|glibc|linux-firmware)(\b|\s|$)' || \
       echo "${CMD}" | grep -qE '\bdnf\s+(remove|erase)\s+-[a-zA-Z0-9]*\*\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Destructive mass package removal is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Mass package purge blocked: ${CMD}"
        exit 2
    fi
```

- [ ] **Step 3: Run test suite to verify generalized blocks pass**

Run: `shellcheck scripts/hooks/pre_tool_guard.sh && tests/test_harness.sh`
Expected: PASS.

- [ ] **Step 4: Commit security guardrail generalization**

```bash
git add scripts/hooks/pre_tool_guard.sh
git commit -m "feat(guardrail): generalize Tier 3 package manager purge blocking across all distributions"
```

---

### Task 4: Refactor Maintenance and Diagnostic Scripts to Use `distro.sh`

**Files:**
- Modify: `scripts/clean_system.sh`
- Modify: `scripts/update_runtimes.sh`
- Modify: `scripts/sys_diag.sh`
- Test: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `scripts/lib/distro.sh`
- Produces: Distribution-agnostic system maintenance, update coordinator, and system health reporting.

- [ ] **Step 1: Refactor `scripts/clean_system.sh`**

```bash
cat <<'EOF' > scripts/clean_system.sh
#!/usr/bin/env bash
# ==============================================================================
# clean_system.sh - Safe Storage, Package & Runtime Cleaner (Cross-Distribution)
# ==============================================================================
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source Distribution Engine
if [ -f "${WORKSPACE_ROOT}/scripts/lib/distro.sh" ]; then
    # shellcheck source=scripts/lib/distro.sh
    source "${WORKSPACE_ROOT}/scripts/lib/distro.sh"
fi

COMPACT_MODE=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --compact|--all)
            COMPACT_MODE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

if [ "${DRY_RUN}" = true ]; then
    echo "==> [DRY RUN] Simulating package and runtime cache cleanups for: ${OS_DISTRO_NAME:-Linux}"
    exit 0
fi

echo "==> [1/4] Cleaning system package caches (${OS_DISTRO_NAME:-Linux})..."
if declare -F pkg_clean >/dev/null 2>&1; then
    pkg_clean || true
elif command -v apt &>/dev/null; then
    sudo apt autoremove -y && sudo apt clean
fi

echo "==> [2/4] Cleaning Python UV tool caches..."
if command -v uv &>/dev/null; then
    uv cache clean || true
fi

echo "==> [3/4] Cleaning PNPM global store & corrupted temp caches..."
if command -v pnpm &>/dev/null; then
    pnpm store prune || true
fi
rm -rf "${HOME}/.cache/puppeteer" 2>/dev/null || true

# Optional: Run compaction if requested
if [ "${COMPACT_MODE}" = true ] && [ -x "${WORKSPACE_ROOT}/scripts/compact_host_disk.sh" ]; then
    echo "==> Triggering host disk compaction..."
    "${WORKSPACE_ROOT}/scripts/compact_host_disk.sh" || true
fi

echo "==> [4/4] Reporting available space:"
df -h /
echo "Cleanup completed safely."
EOF
chmod +x scripts/clean_system.sh
```

- [ ] **Step 2: Refactor `scripts/update_runtimes.sh`**

```bash
cat <<'EOF' > scripts/update_runtimes.sh
#!/usr/bin/env bash
# ==============================================================================
# update_runtimes.sh - Update Runtimes, Toolchains, and Package Repositories
# ==============================================================================
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source Distribution Engine
if [ -f "${WORKSPACE_ROOT}/scripts/lib/distro.sh" ]; then
    # shellcheck source=scripts/lib/distro.sh
    source "${WORKSPACE_ROOT}/scripts/lib/distro.sh"
fi

echo "==> [1/5] Updating system package repositories (${OS_DISTRO_NAME:-Linux})..."
if declare -F pkg_update >/dev/null 2>&1 && declare -F pkg_upgrade >/dev/null 2>&1; then
    pkg_update || true
    pkg_upgrade || true
elif command -v apt &>/dev/null; then
    sudo apt update && sudo apt upgrade -y
fi

echo "==> [2/5] Updating Node / NVM toolchains..."
export NVM_DIR="${HOME}/.nvm"
if [ -s "${NVM_DIR}/nvm.sh" ]; then
    # shellcheck disable=SC1090,SC1091
    source "${NVM_DIR}/nvm.sh"
fi
if command -v corepack &>/dev/null; then
    corepack prepare pnpm@latest --activate 2>/dev/null || true
fi

echo "==> [3/5] Updating Bun runtime..."
if command -v bun &>/dev/null; then
    bun upgrade 2>/dev/null || true
fi

echo "==> [4/5] Updating Astral UV..."
if command -v uv &>/dev/null; then
    uv self update 2>/dev/null || true
fi

echo "==> [5/5] Updating AI Coding and Cloudflare CLIs..."
if command -v npm &>/dev/null; then
    npm install -g @anthropic-ai/claude-code --allow-scripts 2>/dev/null || true
    npm install -g wrangler --allow-scripts 2>/dev/null || true
fi
if command -v agy &>/dev/null; then
    curl -fsSL https://antigravity.google/cli/install.sh | bash 2>/dev/null || true
fi

echo "All runtimes updated."
EOF
chmod +x scripts/update_runtimes.sh
```

- [ ] **Step 3: Refactor `scripts/sys_diag.sh`**

```bash
cat <<'EOF' > scripts/sys_diag.sh
#!/usr/bin/env bash
# ==============================================================================
# sys_diag.sh - Unified System & Environment Diagnostics (Cross-Distribution)
# ==============================================================================
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source Distribution Engine
if [ -f "${WORKSPACE_ROOT}/scripts/lib/distro.sh" ]; then
    # shellcheck source=scripts/lib/distro.sh
    source "${WORKSPACE_ROOT}/scripts/lib/distro.sh"
fi

echo "=============================================================================="
echo "                   SYSTEM & ENVIRONMENT DIAGNOSTICS"
echo "=============================================================================="

echo "==> [1/6] Kernel & OS Identification:"
uname -a
echo "Distribution Family : ${OS_DISTRO_FAMILY:-unknown}"
echo "Distribution Name   : ${OS_DISTRO_NAME:-Linux}"
echo "Package Manager     : ${OS_PKG_MANAGER:-unknown}"

echo -e "\n==> [2/6] Memory & Resource Usage:"
free -h

echo -e "\n==> [3/6] Disk Allocations & File Systems:"
df -h / /mnt/c /mnt/d 2>/dev/null || df -h /

echo -e "\n==> [4/6] Systemd & Service Health:"
if command -v systemctl &>/dev/null; then
    echo "System state: $(systemctl is-system-running 2>&1 || true)"
    FAILED_UNITS=$(systemctl --failed --no-legend 2>&1 || true)
    if [ -z "$FAILED_UNITS" ]; then
        echo "Failed units: None (all healthy)"
    else
        echo "Failed units:"
        echo "$FAILED_UNITS"
    fi
fi

echo -e "\n==> [5/6] Network & Interop Connectivity:"
if ping -c 1 -W 2 1.1.1.1 &>/dev/null; then
    echo "Internet reachability: OK (1.1.1.1 reachable)"
else
    echo "Internet reachability: WARNING (Unable to ping 1.1.1.1)"
fi

echo -e "\n==> [6/6] Developer Toolchains:"
for tool in node pnpm bun uv agy claude wrangler git tmux; do
    if command -v "$tool" &>/dev/null; then
        printf "%-12s: %s (%s)\n" "$tool" "INSTALLED" "$(command -v "$tool")"
    else
        printf "%-12s: %s\n" "$tool" "NOT FOUND"
    fi
done

echo "=============================================================================="
EOF
chmod +x scripts/sys_diag.sh
```

- [ ] **Step 4: Run linters and test harness**

Run: `shellcheck scripts/clean_system.sh scripts/update_runtimes.sh scripts/sys_diag.sh && tests/test_harness.sh`
Expected: PASS.

- [ ] **Step 5: Commit refactored automation scripts**

```bash
git add scripts/clean_system.sh scripts/update_runtimes.sh scripts/sys_diag.sh
git commit -m "refactor(maintenance): adapt clean_system, update_runtimes, and sys_diag to use distro.sh"
```

---

### Task 5: Master Harness Integration and End-to-End Verification

**Files:**
- Modify: `tests/test_harness.sh`
- Test: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `tests/test_distro.sh`, `scripts/lib/distro.sh`
- Produces: Extended 26-assertion master test suite verifying cross-distro detection and generalized safety invariants.

- [ ] **Step 1: Integrate Cross-Distribution Assertions into `tests/test_harness.sh`**

```bash
cat <<'EOF' > tests/test_harness.sh
#!/usr/bin/env bash
# tests/test_harness.sh - Test suite for os-manager Claude Harness
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOOKS_DIR="${WORKSPACE_ROOT}/scripts/hooks"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

assert_exit_code() {
    local test_name="$1"
    local expected_code="$2"
    local actual_code="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ "${actual_code}" -eq "${expected_code}" ]; then
        echo "  [PASS] ${test_name} (exit code: ${actual_code})"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (expected: ${expected_code}, got: ${actual_code})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running Claude Code Harness Test Suite"
echo "=================================================="

echo "--- Testing Session Preflight & Cleanup Hooks ---"
set +e
"${HOOKS_DIR}/session_preflight.sh" > /dev/null 2>&1
assert_exit_code "session_preflight.sh execution" 0 $?

"${HOOKS_DIR}/session_cleanup.sh" > /dev/null 2>&1
assert_exit_code "session_cleanup.sh execution" 0 $?
set -e

echo "--- Testing PreToolGuard 4-Tier Security Matrix ---"
set +e

# Tier 0 Allow: git status
PAYLOAD_TIER0='{"tool_name":"Bash","tool_input":{"command":"git status"}}'
echo "${PAYLOAD_TIER0}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 0 Read-Only Command (git status)" 0 $?

# Tier 1 Allow: Workspace file edit
PAYLOAD_TIER1="{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"${WORKSPACE_ROOT}/CLAUDE.md\",\"old_string\":\"a\",\"new_string\":\"b\"}}"
echo "${PAYLOAD_TIER1}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 1 Workspace Contained Edit" 0 $?

# Tier 2 Allow: Maintenance script
PAYLOAD_TIER2='{"tool_name":"Bash","tool_input":{"command":"./scripts/sys_diag.sh"}}'
echo "${PAYLOAD_TIER2}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 2 Whitelisted Script (sys_diag.sh)" 0 $?

# Tier 2 Allow: Performance benchmark script
PAYLOAD_TIER2_PERF='{"tool_name":"Bash","tool_input":{"command":"./scripts/perf_tune.sh"}}'
echo "${PAYLOAD_TIER2_PERF}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 2 Whitelisted Script (perf_tune.sh)" 0 $?

# Tier 2 Allow: Timer manager script
PAYLOAD_TIER2_TIMERS='{"tool_name":"Bash","tool_input":{"command":"./scripts/manage_timers.sh"}}'
echo "${PAYLOAD_TIER2_TIMERS}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 2 Whitelisted Script (manage_timers.sh)" 0 $?

# Tier 2 Allow: Hook benchmark script
PAYLOAD_TIER2_BENCH='{"tool_name":"Bash","tool_input":{"command":"./scripts/hook_benchmark.sh --summary"}}'
echo "${PAYLOAD_TIER2_BENCH}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 2 Whitelisted Script (hook_benchmark.sh)" 0 $?

# Tier 3 Block: Root obliteration
PAYLOAD_TIER3_ROOT='{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}'
echo "${PAYLOAD_TIER3_ROOT}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (rm -rf /)" 2 $?

# Tier 3 Block: WSL lifecycle sabotage
PAYLOAD_TIER3_WSL='{"tool_name":"Bash","tool_input":{"command":"wsl.exe --unregister Debian"}}'
echo "${PAYLOAD_TIER3_WSL}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (wsl --unregister)" 2 $?

# Tier 3 Block: Windows System Host Write
PAYLOAD_TIER3_WIN='{"tool_name":"Write","tool_input":{"file_path":"/mnt/c/Windows/System32/drivers/etc/hosts","content":"127.0.0.1 test"}}'
echo "${PAYLOAD_TIER3_WIN}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (Windows System Host Write)" 2 $?

# Tier 3 Block: Container Privilege Escalation
PAYLOAD_TIER3_PODMAN='{"tool_name":"Bash","tool_input":{"command":"podman run --privileged ubuntu bash"}}'
echo "${PAYLOAD_TIER3_PODMAN}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (podman run --privileged)" 2 $?

# Tier 3 Block: APT Wildcard Purge
PAYLOAD_TIER3_APT='{"tool_name":"Bash","tool_input":{"command":"apt purge *"}}'
echo "${PAYLOAD_TIER3_APT}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (apt purge *)" 2 $?

# Tier 3 Block: Pacman Wildcard Removal
PAYLOAD_TIER3_PACMAN='{"tool_name":"Bash","tool_input":{"command":"pacman -Rcs *"}}'
echo "${PAYLOAD_TIER3_PACMAN}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (pacman -Rcs *)" 2 $?

# Tier 3 Block: DNF Mass Removal
PAYLOAD_TIER3_DNF='{"tool_name":"Bash","tool_input":{"command":"dnf remove --all"}}'
echo "${PAYLOAD_TIER3_DNF}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (dnf remove --all)" 2 $?

# Tier 3 Block: Zypper Wildcard Removal
PAYLOAD_TIER3_ZYPPER='{"tool_name":"Bash","tool_input":{"command":"zypper remove *"}}'
echo "${PAYLOAD_TIER3_ZYPPER}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (zypper remove *)" 2 $?

echo "--- Testing PostToolUse Auto-Healing Linting ---"

# Test valid bash file passes
TEMP_VALID_BASH="/tmp/os_manager_test_valid.sh"
echo -e '#!/usr/bin/env bash\necho "hello"' > "${TEMP_VALID_BASH}"
PAYLOAD_VALID_BASH="{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"${TEMP_VALID_BASH}\"}}"
echo "${PAYLOAD_VALID_BASH}" | "${HOOKS_DIR}/post_tool_lint.sh" > /dev/null 2>&1
assert_exit_code "PostToolUse Valid Bash Script" 0 $?
rm -f "${TEMP_VALID_BASH}"

# Test invalid bash syntax fails with Exit 2
TEMP_INVALID_BASH="/tmp/os_manager_test_invalid.sh"
echo -e '#!/usr/bin/env bash\nif [ a == b ]; then echo missing fi' > "${TEMP_INVALID_BASH}"
PAYLOAD_INVALID_BASH="{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"${TEMP_INVALID_BASH}\"}}"
echo "${PAYLOAD_INVALID_BASH}" | "${HOOKS_DIR}/post_tool_lint.sh" > /dev/null 2>&1
assert_exit_code "PostToolUse Invalid Bash Script (Auto-Healing Exit 2)" 2 $?
rm -f "${TEMP_INVALID_BASH}"

# Test valid JSON file passes
TEMP_VALID_JSON="/tmp/os_manager_test_valid.json"
echo '{"status":"ok"}' > "${TEMP_VALID_JSON}"
PAYLOAD_VALID_JSON="{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"${TEMP_VALID_JSON}\"}}"
echo "${PAYLOAD_VALID_JSON}" | "${HOOKS_DIR}/post_tool_lint.sh" > /dev/null 2>&1
assert_exit_code "PostToolUse Valid JSON File" 0 $?
rm -f "${TEMP_VALID_JSON}"

# Test invalid JSON syntax fails with Exit 2
TEMP_INVALID_JSON="/tmp/os_manager_test_invalid.json"
echo '{"status": invalid_json' > "${TEMP_INVALID_JSON}"
PAYLOAD_INVALID_JSON="{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"${TEMP_INVALID_JSON}\"}}"
echo "${PAYLOAD_INVALID_JSON}" | "${HOOKS_DIR}/post_tool_lint.sh" > /dev/null 2>&1
assert_exit_code "PostToolUse Invalid JSON File (Auto-Healing Exit 2)" 2 $?
rm -f "${TEMP_INVALID_JSON}"

echo "--- Testing Failure Telemetry & Pre-Compact Snapshot ---"
PAYLOAD_FAIL='{"error":"command not found"}'
echo "${PAYLOAD_FAIL}" | "${HOOKS_DIR}/post_tool_failure.sh" > /dev/null 2>&1
assert_exit_code "post_tool_failure.sh execution" 0 $?

"${HOOKS_DIR}/pre_compact_state.sh" > /dev/null 2>&1
assert_exit_code "pre_compact_state.sh execution" 0 $?

echo "--- Testing Hook Performance Tracing Unit Suite ---"
set +e
"${WORKSPACE_ROOT}/tests/test_hook_tracing.sh" > /dev/null 2>&1
assert_exit_code "test_hook_tracing.sh complete suite" 0 $?

echo "--- Testing Cross-Distribution Discovery Unit Suite ---"
"${WORKSPACE_ROOT}/tests/test_distro.sh" > /dev/null 2>&1
assert_exit_code "test_distro.sh complete suite" 0 $?
set -e

echo "--- Testing Skills Frontmatter & SDO Compliance ---"
validate_skills_frontmatter() {
    local skill_dir="${WORKSPACE_ROOT}/.claude/skills"
    local invalid_count=0
    local total_skills=0

    for skill_file in "${skill_dir}"/*/SKILL.md; do
        [ -f "${skill_file}" ] || continue
        total_skills=$((total_skills + 1))

        local first_line
        first_line="$(head -n 1 "${skill_file}")"
        if [ "${first_line}" != "---" ]; then
            invalid_count=$((invalid_count + 1))
            continue
        fi

        local end_line
        end_line="$(awk 'NR > 1 && /^---$/ { print NR; exit }' "${skill_file}")"
        if [ -z "${end_line}" ]; then
            invalid_count=$((invalid_count + 1))
            continue
        fi

        local frontmatter
        frontmatter="$(sed -n "2,$((end_line - 1))p" "${skill_file}")"

        if ! echo "${frontmatter}" | grep -qE '^name:[[:space:]]+.+'; then
            invalid_count=$((invalid_count + 1))
            continue
        fi

        if ! echo "${frontmatter}" | grep -qE '^description:[[:space:]]+.+'; then
            invalid_count=$((invalid_count + 1))
            continue
        fi

        local desc_val
        desc_val="$(echo "${frontmatter}" | grep -E '^description:' | head -n 1 | sed -E 's/^description:[[:space:]]*//; s/^["'"'"']//')"
        case "${desc_val}" in
            "Use when"*|"You MUST use this"*)
                ;;
            *)
                invalid_count=$((invalid_count + 1))
                continue
                ;;
        esac
    done

    if [ "${total_skills}" -eq 0 ] || [ "${invalid_count}" -gt 0 ]; then
        return 1
    fi
    return 0
}

validate_skills_frontmatter > /dev/null 2>&1
assert_exit_code "All Skills Frontmatter & SDO Compliance" 0 $?

echo "--- Testing Automation & Resilience Components ---"

set +e
"${WORKSPACE_ROOT}/scripts/perf_tune.sh" --quick > /dev/null 2>&1
assert_exit_code "perf_tune.sh --quick execution" 0 $?

validate_systemd_units() {
    local service_file="${WORKSPACE_ROOT}/systemd/os-maintenance.service"
    local timer_file="${WORKSPACE_ROOT}/systemd/os-maintenance.timer"

    if [ ! -f "${service_file}" ] || [ ! -f "${timer_file}" ]; then
        return 1
    fi

    if command -v systemd-analyze >/dev/null 2>&1; then
        systemd-analyze verify "${service_file}" "${timer_file}" > /dev/null 2>&1 || return 1
    fi
    return 0
}
validate_systemd_units
assert_exit_code "Systemd Unit Files & Syntax Validation" 0 $?

validate_playbooks() {
    local dotfiles_pb="${WORKSPACE_ROOT}/playbooks/dotfiles_sync.md"
    local disaster_pb="${WORKSPACE_ROOT}/playbooks/disaster_recovery.md"

    if [ ! -f "${dotfiles_pb}" ] || [ ! -f "${disaster_pb}" ]; then
        return 1
    fi

    if command -v agent-style >/dev/null 2>&1; then
        agent-style review --audit-only "${dotfiles_pb}" > /dev/null 2>&1 || return 1
        agent-style review --audit-only "${disaster_pb}" > /dev/null 2>&1 || return 1
    fi
    return 0
}
validate_playbooks
assert_exit_code "Playbooks Existence & Style Compliance" 0 $?

set -e

echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
EOF
chmod +x tests/test_harness.sh
```

- [ ] **Step 2: Run test suite to verify full integration**

Run: `tests/test_harness.sh`
Expected: PASS (All 27 assertions pass).

- [ ] **Step 3: Commit master test harness update**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate cross-distribution discovery and safety assertions into test_harness.sh"
```
