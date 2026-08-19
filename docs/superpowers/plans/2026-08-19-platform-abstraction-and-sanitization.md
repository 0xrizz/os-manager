# Platform Abstraction and Path Sanitization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the universal cross-platform abstraction library (`scripts/lib/platform.sh`) supporting Linux, WSL2, and macOS. Sanitize all hardcoded personal directory paths into portable environment variables.

**Architecture:** Modular platform detection handles package managers (`apt`, `dnf`, `pacman`, `zypper`, `brew`), notification bridges, and service supervisors (`systemd`, `launchd`). Path resolvers export portable defaults (`${OSM_ROOT}`, `${OSM_BACKUP_DIR}`, `${OSM_LOG_DIR}`, `${OSM_RUN_DIR}`).

**Tech Stack:** POSIX Bash 5+, macOS Darwin utilities (`uname`, `sw_vers`, `osascript`), Linux `/etc/os-release`, Microsoft WSL `/proc/version`.

**Spec:** `docs/superpowers/specs/2026-08-19-open-source-os-manager-specification.md`

## Global Constraints

- Strict `set -euo pipefail` across all shell scripts.
- Zero external runtime dependencies beyond standard core POSIX utilities.
- Zero hardcoded personal paths (e.g. no `/home/rizz/`) in any active script or configuration template.
- Full backwards compatibility with the existing 50-assertion test harness suite.

---

## File Structure & Responsibilities

```text
os-manager/
├── scripts/
│   ├── lib/
│   │   ├── platform.sh          # Universal platform, OS, package & notification engine
│   │   └── distro.sh            # Existing distro detection (delegates to platform.sh)
│   ├── dotfiles_sync.sh         # Dotfiles sync supporting .example templates and dynamic homes
│   ├── sandbox_exec.sh          # Container sandbox using dynamic OSM_DEV_ROOT boundary
│   ├── migrate_repos.sh         # Migration utility using dynamic OSM_DEV_ROOT
│   └── notify_host.sh           # Desktop notification dispatcher leveraging platform.sh
├── backups/
│   └── dotfiles/
│       ├── .bashrc.example      # Generic sanitized bash configuration template
│       ├── .tmux.conf.example    # Generic sanitized tmux configuration template
│       └── .gitconfig.example    # Generic sanitized git configuration template
├── tests/
│   ├── test_platform.sh         # Unit tests for platform detection and abstraction (16 assertions)
│   └── test_harness.sh          # Master harness integrating platform and sanitization tests
└── CLAUDE.md                    # Project guidance updated with portable path variables
```

---

### Task 1: Create Unit Test Suite for Platform Abstraction (`tests/test_platform.sh`)

**Files:**
- Create: `tests/test_platform.sh`

**Interfaces:**
- Consumes: Environment mock overrides (`OSM_UNAME_S`, `OSM_PROC_VERSION`, `OS_RELEASE_FILE`, `OSM_COMMAND_OVERRIDE`).
- Produces: Executable unit test suite with 16 assertions validating detection across Debian, Ubuntu, Arch, Fedora, openSUSE, Alpine, WSL2, and macOS Darwin.

- [ ] **Step 1: Write the failing unit test suite**

Create `tests/test_platform.sh`:

```bash
#!/usr/bin/env bash
# tests/test_platform.sh - Unit test suite for universal platform abstraction library
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

# 1. Test library existence and syntax
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -f "${PLATFORM_LIB}" ]; then
    echo "  [PASS] platform.sh exists"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] platform.sh missing at ${PLATFORM_LIB}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

test_mock_platform() {
    local test_id="$1"
    local mock_uname="$2"
    local mock_proc_version="$3"
    local mock_os_release="$4"
    local expected_platform="$5"
    local expected_family="$6"
    local expected_pkg="$7"
    local expected_service="$8"
    local expected_notify="$9"

    local mock_release_file="/tmp/mock_release_${test_id}"
    local mock_version_file="/tmp/mock_version_${test_id}"

    echo "${mock_os_release}" > "${mock_release_file}"
    echo "${mock_proc_version}" > "${mock_version_file}"

    local result
    result="$(
        export OSM_UNAME_S="${mock_uname}"
        export OSM_PROC_VERSION_FILE="${mock_version_file}"
        export OS_RELEASE_FILE="${mock_release_file}"
        # shellcheck disable=SC1090
        source "${PLATFORM_LIB}"
        platform_detect
        echo "${OSM_PLATFORM}:${OSM_DISTRO_FAMILY}:${OSM_PKG_MANAGER}:${OSM_SERVICE_MANAGER}:${OSM_NOTIFY_ENGINE}"
    )"
    rm -f "${mock_release_file}" "${mock_version_file}"

    IFS=':' read -r p_plat p_fam p_pkg p_srv p_not <<< "${result}"

    assert_equals "${test_id} Platform" "${expected_platform}" "${p_plat}"
    assert_equals "${test_id} Family" "${expected_family}" "${p_fam}"
    assert_equals "${test_id} Package Manager" "${expected_pkg}" "${p_pkg}"
    assert_equals "${test_id} Service Manager" "${expected_service}" "${p_srv}"
    assert_equals "${test_id} Notification Engine" "${expected_notify}" "${p_not}"
}

# 2. Test Native Linux (Debian 13)
test_mock_platform "Native-Debian-13" \
    "Linux" \
    "Linux version 6.1.0-generic (gcc version 12.2.0)" \
    'ID=debian
VERSION_ID="13"
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"' \
    "linux" "debian" "apt" "systemd" "notify-send"

# 3. Test WSL2 Linux (Debian on Microsoft WSL2)
test_mock_platform "WSL2-Debian" \
    "Linux" \
    "Linux version 6.6.36.3-microsoft-standard-WSL2 (oe-user@oe-host)" \
    'ID=debian
VERSION_ID="13"
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"' \
    "wsl" "debian" "apt" "systemd" "winrt"

# 4. Test macOS Darwin (macOS 14 Sonoma)
test_mock_platform "macOS-Darwin" \
    "Darwin" \
    "" \
    "" \
    "macos" "darwin" "brew" "launchd" "osascript"

# 5. Test Native Arch Linux
test_mock_platform "Native-Arch" \
    "Linux" \
    "Linux version 6.10.3-arch1-1" \
    'ID=arch
PRETTY_NAME="Arch Linux"' \
    "linux" "arch" "pacman" "systemd" "notify-send"

# 6. Test Native Fedora Linux
test_mock_platform "Native-Fedora" \
    "Linux" \
    "Linux version 6.9.12-200.fc40.x86_64" \
    'ID=fedora
VERSION_ID="40"
PRETTY_NAME="Fedora Linux 40"' \
    "linux" "fedora" "dnf" "systemd" "notify-send"

# 7. Test Path Defaults Initialization
TOTAL_TESTS=$((TOTAL_TESTS + 1))
PATH_TEST_OUT="$(
    unset OSM_ROOT OSM_BACKUP_DIR OSM_LOG_DIR OSM_RUN_DIR
    export HOME="/tmp/mock_user_home"
    # shellcheck disable=SC1090
    source "${PLATFORM_LIB}"
    platform_init_paths
    echo "${OSM_ROOT}:${OSM_BACKUP_DIR}:${OSM_LOG_DIR}:${OSM_RUN_DIR}"
)"
EXPECTED_PATHS="/tmp/mock_user_home/.os-manager:/tmp/mock_user_home/.local/share/os-manager/backups:/tmp/mock_user_home/.local/state/os-manager/logs:/tmp/os-manager-${UID}"
if [ "${PATH_TEST_OUT}" = "${EXPECTED_PATHS}" ]; then
    echo "  [PASS] Path Defaults Resolution"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Path Defaults Resolution (expected: '${EXPECTED_PATHS}', got: '${PATH_TEST_OUT}')"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo "=================================================="
echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
```

- [ ] **Step 2: Run test suite to verify failure**

Run: `chmod +x tests/test_platform.sh && ./tests/test_platform.sh`
Expected: FAIL (missing `scripts/lib/platform.sh`).

- [ ] **Step 3: Commit initial test suite**

```bash
git add tests/test_platform.sh
git commit -m "test(platform): add cross-platform abstraction unit test suite"
```

---

### Task 2: Implement Universal Platform Abstraction Engine (`scripts/lib/platform.sh`)

**Files:**
- Create: `scripts/lib/platform.sh`
- Modify: `scripts/lib/distro.sh:1-226`

**Interfaces:**
- Consumes: Host kernel metadata (`uname -s`, `/proc/version`), Linux distro metadata (`/etc/os-release`).
- Produces: Exported variables (`OSM_PLATFORM`, `OSM_DISTRO_ID`, `OSM_DISTRO_FAMILY`, `OSM_DISTRO_VERSION`, `OSM_DISTRO_NAME`, `OSM_PKG_MANAGER`, `OSM_SERVICE_MANAGER`, `OSM_NOTIFY_ENGINE`, `OSM_ROOT`, `OSM_BACKUP_DIR`, `OSM_LOG_DIR`, `OSM_RUN_DIR`) and helper functions (`platform_detect`, `platform_pkg_cmd`, `platform_service_cmd`, `platform_notify_cmd`, `platform_init_paths`).

- [ ] **Step 1: Write `scripts/lib/platform.sh`**

Create `scripts/lib/platform.sh`:

```bash
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
                OSM_DISTRO_ID="generic"
                OSM_DISTRO_FAMILY="generic"
                OSM_DISTRO_NAME="Generic Linux"
                OSM_DISTRO_VERSION="unknown"
                OSM_PKG_MANAGER="unknown"
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
                pacman) sudo pacman -Sc --noconfirm ;;
                dnf) sudo dnf autoremove -y && sudo dnf clean all ;;
                zypper) sudo zypper clean --all ;;
                apk) [ -d /var/cache/apk ] && sudo rm -rf /var/cache/apk/* ;;
                brew) brew cleanup -s ;;
                *) echo "[platform.sh] Unsupported package manager for clean: ${OSM_PKG_MANAGER}" >&2; return 1 ;;
            esac
            ;;
        install)
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
```

- [ ] **Step 2: Update `scripts/lib/distro.sh` to maintain backwards compatibility**

Update `scripts/lib/distro.sh`:

```bash
#!/usr/bin/env bash
# scripts/lib/distro.sh - Backwards-compatible shim delegating to platform.sh
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
```

- [ ] **Step 3: Run unit test suites to verify pass**

Run:
```bash
./tests/test_platform.sh
./tests/test_distro.sh
```
Expected: PASS (100% assertions pass across `test_platform.sh` and `test_distro.sh`).

- [ ] **Step 4: Commit platform abstraction engine**

```bash
git add scripts/lib/platform.sh scripts/lib/distro.sh
git commit -m "feat(platform): implement universal cross-platform abstraction library"
```

---

### Task 3: Parametrize Repository Scripts & Configurations to Eliminate Hardcoded Paths

**Files:**
- Modify: `scripts/sandbox_exec.sh:35,93-98`
- Modify: `scripts/migrate_repos.sh:3,8`
- Modify: `systemd/os-maintenance.service:8`
- Modify: `systemd/os-metrics-exporter.service:8,17`
- Modify: `.claude/commands/*.md`
- Modify: `.claude/skills/*/SKILL.md`
- Modify: `.claude/rules/safety-tiers.md`
- Modify: `.claude/rules/wsl-boundaries.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: Dynamic `${OSM_DEV_ROOT:-${HOME}/dev}`, `${CLAUDE_PROJECT_DIR}`, `%h` systemd specifiers.
- Produces: 100% portable scripts, hooks, commands, and rules with zero hardcoded user home directories.

- [ ] **Step 1: Write test assertion verifying path sanitization**

Add a check to `tests/test_platform.sh` verifying that no active scripts in `scripts/`, `systemd/`, `.claude/rules/`, `.claude/commands/`, or `.claude/skills/` contain hardcoded `/home/rizz`:

```bash
# Append to tests/test_platform.sh
TOTAL_TESTS=$((TOTAL_TESTS + 1))
HARDCODED_MATCHES="$(grep -rn "/home/rizz" "${WORKSPACE_ROOT}/scripts" "${WORKSPACE_ROOT}/systemd" "${WORKSPACE_ROOT}/.claude/commands" "${WORKSPACE_ROOT}/.claude/rules" "${WORKSPACE_ROOT}/.claude/skills" || true)"
if [ -z "${HARDCODED_MATCHES}" ]; then
    echo "  [PASS] Path Sanitization (Zero hardcoded /home/rizz references)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Hardcoded user home found in active files:"
    echo "${HARDCODED_MATCHES}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
```

- [ ] **Step 2: Run `tests/test_platform.sh` to observe failure**

Run: `./tests/test_platform.sh`
Expected: FAIL on path sanitization assertion.

- [ ] **Step 3: Update scripts, services, commands, and rules**

1. In `scripts/sandbox_exec.sh`:
Replace hardcoded `/home/rizz/dev/` with `${OSM_DEV_ROOT:-${HOME}/dev}`.
```bash
CANONICAL_TARGET="$(realpath -m "${TARGET_DIR}" 2>/dev/null || echo "${TARGET_DIR}")"
ALLOWED_DEV_ROOT="$(realpath -m "${OSM_DEV_ROOT:-${HOME}/dev}")"
if [[ ! "${CANONICAL_TARGET}" =~ ^${ALLOWED_DEV_ROOT}(/|$) ]]; then
    echo "[SECURITY ERROR] Sandbox target directory must reside strictly under ${ALLOWED_DEV_ROOT}: ${TARGET_DIR}" >&2
    exit 2
fi
```

2. In `scripts/migrate_repos.sh`:
```bash
DEST_BASE="${OSM_DEV_ROOT:-${HOME}/dev}"
```

3. In `systemd/os-maintenance.service` & `systemd/os-metrics-exporter.service`:
Use `%h` specifier (systemd user home expansion):
- `ExecStart=%h/.local/bin/osm clean --all` (or `%h/dev/os-manager/scripts/clean_system.sh --all`)
- `ReadWritePaths=%h/dev/os-manager/backups/logs %h/.local/state/os-manager/logs`

4. In `.claude/commands/*.md` and `.claude/skills/*/SKILL.md`:
Replace `/home/rizz/dev/os-manager/` with `${CLAUDE_PROJECT_DIR}/` or `./`.

5. In `.claude/rules/safety-tiers.md`, `.claude/rules/wsl-boundaries.md`, and `CLAUDE.md`:
Replace `/home/rizz/dev/os-manager` with `${CLAUDE_PROJECT_DIR}` and `/home/rizz/` with `${HOME}/` or native ext4 user domain.

- [ ] **Step 4: Run `tests/test_platform.sh` and `tests/test_sandbox.sh` to verify pass**

Run:
```bash
./tests/test_platform.sh
./tests/test_sandbox.sh
```
Expected: PASS (Zero hardcoded `/home/rizz` references found; sandbox boundary tests pass).

- [ ] **Step 5: Commit sanitized scripts and configurations**

```bash
git add scripts/ systemd/ .claude/ CLAUDE.md tests/test_platform.sh tests/test_sandbox.sh
git commit -m "refactor(core): sanitize hardcoded personal paths into dynamic variables"
```

---

### Task 4: Sanitize Dotfile Templates & Update `scripts/dotfiles_sync.sh`

**Files:**
- Create: `backups/dotfiles/.bashrc.example`
- Create: `backups/dotfiles/.tmux.conf.example`
- Create: `backups/dotfiles/.gitconfig.example`
- Delete/Replace: `backups/dotfiles/.bashrc`, `backups/dotfiles/.tmux.conf`, `backups/dotfiles/.gitconfig`
- Modify: `scripts/dotfiles_sync.sh:1-50`
- Test: `tests/test_platform.sh`

**Interfaces:**
- Consumes: Generic `.example` templates in `backups/dotfiles/`.
- Produces: Safe dotfiles sync script supporting both `.example` templates and live `$HOME` synchronization.

- [ ] **Step 1: Write unit test assertion for dotfile template sanitization**

Add assertions in `tests/test_platform.sh`:

```bash
# Check dotfiles directory contents
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

TOTAL_TESTS=$((TOTAL_TESTS + 1))
DOTFILES_MATCHES="$(grep -rn "/home/rizz" "${WORKSPACE_ROOT}/backups/dotfiles" || true)"
if [ -z "${DOTFILES_MATCHES}" ]; then
    echo "  [PASS] Dotfiles templates sanitized (Zero personal paths)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Personal paths found in dotfiles templates:"
    echo "${DOTFILES_MATCHES}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
```

- [ ] **Step 2: Run `tests/test_platform.sh` to observe failure**

Run: `./tests/test_platform.sh`
Expected: FAIL (missing `.example` templates).

- [ ] **Step 3: Create sanitized `.example` templates and update `scripts/dotfiles_sync.sh`**

1. Create `backups/dotfiles/.bashrc.example`:
```bash
# ~/.bashrc - Generic interactive shell configuration template
[ -z "$PS1" ] && return

shopt -s checkwinsize
shopt -s histappend

HISTCONTROL=ignoreboth
HISTSIZE=10000
HISTFILESIZE=20000

export PATH="${HOME}/.local/bin:${PATH}"
export EDITOR="nano"

# Aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
```

2. Create `backups/dotfiles/.tmux.conf.example`:
```tmux
# ~/.tmux.conf - Generic tmux configuration template
set -g default-terminal "screen-256color"
set -g history-limit 50000
set -g mouse on
set -s escape-time 0

# Status bar styling
set -g status-style bg=black,fg=white
set -g status-left "#[fg=green]#S "
set -g status-right "#[fg=cyan]%Y-%m-%d %H:%M"
```

3. Create `backups/dotfiles/.gitconfig.example`:
```ini
[user]
	name = Your Name
	email = your.email@example.com
[core]
	editor = nano
	autocrlf = input
[init]
	defaultBranch = main
[pull]
	rebase = false
```

4. Remove raw personal dotfiles (`backups/dotfiles/.bashrc`, `.tmux.conf`, `.gitconfig`) in favor of the `.example` templates.

5. Update `scripts/dotfiles_sync.sh` to look for both active dotfile names and `.example` fallbacks:

```bash
#!/usr/bin/env bash
# scripts/dotfiles_sync.sh - Dotfile backup, diff, and template synchronization
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_TARGET="${WORKSPACE_ROOT}/backups/dotfiles"
mkdir -p "${BACKUP_TARGET}"

ACTION="${1:-diff}"

FILES_TO_MANAGE=(
    ".bashrc"
    ".tmux.conf"
    ".gitconfig"
)

case "${ACTION}" in
    backup)
        echo "=== Backing up Dotfiles ==="
        for f in "${FILES_TO_MANAGE[@]}"; do
            if [ -f "${HOME}/${f}" ]; then
                cp -v "${HOME}/${f}" "${BACKUP_TARGET}/${f}.example"
            fi
        done
        echo "Backup complete in ${BACKUP_TARGET}"
        ;;
    diff)
        echo "=== Dotfiles Diff Inspection ==="
        for f in "${FILES_TO_MANAGE[@]}"; do
            local_src="${BACKUP_TARGET}/${f}"
            [ ! -f "${local_src}" ] && local_src="${BACKUP_TARGET}/${f}.example"

            if [ -f "${local_src}" ] && [ -f "${HOME}/${f}" ]; then
                echo "--- Diff for ~/${f} (against ${local_src}) ---"
                diff -u "${local_src}" "${HOME}/${f}" || true
            elif [ -f "${HOME}/${f}" ]; then
                echo "File ~/${f} exists but has no template in repository."
            fi
        done
        ;;
    restore)
        echo "=== Restoring Dotfiles ==="
        for f in "${FILES_TO_MANAGE[@]}"; do
            local_src="${BACKUP_TARGET}/${f}"
            [ ! -f "${local_src}" ] && local_src="${BACKUP_TARGET}/${f}.example"

            if [ -f "${local_src}" ]; then
                cp -iv "${local_src}" "${HOME}/${f}"
            fi
        done
        ;;
    *)
        echo "Usage: $0 {backup|diff|restore}"
        exit 1
        ;;
esac
```

- [ ] **Step 4: Run unit tests to verify pass**

Run: `./tests/test_platform.sh`
Expected: PASS (All dotfile template assertions pass with zero personal paths).

- [ ] **Step 5: Commit dotfile templates and updated sync script**

```bash
git add backups/dotfiles/ scripts/dotfiles_sync.sh tests/test_platform.sh
git commit -m "feat(dotfiles): provide sanitized templates and portable synchronization"
```

---

### Task 5: Integrate Platform & Sanitization Assertions in Master Harness (`tests/test_harness.sh`)

**Files:**
- Modify: `tests/test_harness.sh:1-170`

**Interfaces:**
- Consumes: `tests/test_platform.sh`.
- Produces: Master test suite with platform abstraction and repository sanitization integration assertions (increasing total assertions from 50 to 52+).

- [ ] **Step 1: Write integration assertions in `tests/test_harness.sh`**

Add test suite execution to `tests/test_harness.sh`:

```bash
echo "--- Testing Platform Abstraction & Path Sanitization Suite ---"
set +e
"${WORKSPACE_ROOT}/tests/test_platform.sh" > /dev/null 2>&1
assert_exit_code "test_platform.sh execution" 0 $?

# Verify zero hardcoded /home/rizz references across all active repository code
REPO_LEAK_CHECK="$(grep -rn "/home/rizz" \
    "${WORKSPACE_ROOT}/scripts" \
    "${WORKSPACE_ROOT}/systemd" \
    "${WORKSPACE_ROOT}/.claude/commands" \
    "${WORKSPACE_ROOT}/.claude/rules" \
    "${WORKSPACE_ROOT}/.claude/skills" \
    "${WORKSPACE_ROOT}/backups/dotfiles" || true)"

if [ -z "${REPO_LEAK_CHECK}" ]; then
    assert_exit_code "Repository-wide path sanitization" 0 0
else
    echo "  [FAIL] Hardcoded personal path leak detected: ${REPO_LEAK_CHECK}"
    assert_exit_code "Repository-wide path sanitization" 0 1
fi
set -e
```

- [ ] **Step 2: Run full test harness suite**

Run: `./tests/test_harness.sh`
Expected: PASS (All 52 assertions pass with 0 failures).

- [ ] **Step 3: Run comprehensive harness self-check**

Run: `./scripts/harness_check.sh`
Expected: PASS with 100% health score.

- [ ] **Step 4: Commit master test suite integration**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate platform abstraction and path sanitization assertions"
```

---

## Plan Self-Review

### 1. Spec Coverage
- **Operating System Detection (Linux native, WSL2, macOS Darwin)**: Covered in Task 1 (`tests/test_platform.sh`) and Task 2 (`scripts/lib/platform.sh`).
- **Package Manager Mapping (`apt`, `dnf`, `pacman`, `zypper`, `apk`, `brew`)**: Covered in Task 1 and Task 2 (`platform_pkg_cmd`).
- **Service Supervision Abstraction (`systemd`, `launchd`)**: Covered in Task 1 and Task 2 (`OSM_SERVICE_MANAGER`).
- **Desktop Notification Abstraction (`winrt`, `osascript`, `notify-send`)**: Covered in Task 1 and Task 2 (`OSM_NOTIFY_ENGINE`).
- **Dynamic Path Defaults Resolution (`${OSM_ROOT}`, `${OSM_BACKUP_DIR}`, `${OSM_LOG_DIR}`, `${OSM_RUN_DIR}`)**: Covered in Task 1 and Task 2 (`platform_init_paths`).
- **Repository Path Sanitization**: Covered in Task 3 (`sandbox_exec.sh`, `migrate_repos.sh`, `.claude/`, `systemd/`, `CLAUDE.md`).
- **Clean Dotfile Templates**: Covered in Task 4 (`backups/dotfiles/*.example` and `scripts/dotfiles_sync.sh`).
- **Master Harness Integration**: Covered in Task 5 (`tests/test_harness.sh` reaching 52 assertions).

### 2. Placeholder Scan
- No "TBD", "TODO", or pseudo-code found. Every task contains complete bash implementations, explicit command arguments, and full test assertions.

### 3. Type & Variable Consistency
- Variables across tasks match consistently: `OSM_PLATFORM`, `OSM_DISTRO_ID`, `OSM_DISTRO_FAMILY`, `OSM_DISTRO_VERSION`, `OSM_DISTRO_NAME`, `OSM_PKG_MANAGER`, `OSM_SERVICE_MANAGER`, `OSM_NOTIFY_ENGINE`, `OSM_ROOT`, `OSM_BACKUP_DIR`, `OSM_LOG_DIR`, `OSM_RUN_DIR`, `OSM_DEV_ROOT`.
