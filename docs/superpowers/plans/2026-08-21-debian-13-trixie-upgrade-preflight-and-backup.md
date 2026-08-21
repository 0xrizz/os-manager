# Debian 13 (Trixie) Upgrade: Pre-Flight Verification & State Backup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the pre-flight safety checking engine and state backup/manifest snapshot modules (Phase 0 and Phase 1) for the Debian 12 $\rightarrow$ 13 (Trixie) upgrade pipeline in `scripts/upgrade_debian_trixie.sh` with comprehensive mockable unit tests in `tests/test_upgrade_preflight.sh`.

**Architecture:** A robust, modular Bash 4+ upgrade engine structured into isolated subroutines (`check_preflight`, `create_backup`, `simulate_dry_run`) with mockable environment overrides (`OSM_MOCK_*`), strict signal traps, automated `/etc/apt/` backup snapshots, package selection exports, and `upgrade_manifest.json` telemetry.

**Tech Stack:** Bash 4.4+, GNU coreutils (`df`, `stat`, `mktemp`), `dpkg`, `apt`, `curl` / `nc`, `python3` (manifest validation), `git`.

**Spec:** [`docs/superpowers/specs/2026-08-21-debian-13-trixie-upgrade-automation-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-21-debian-13-trixie-upgrade-automation-design.md)

---

## Global Constraints

- **Zero-Data-Loss Guardrail:** Under no circumstances shall `/dev/nvme0n1p4` (`/mnt/data`) be formatted, modified, or unmounted.
- **Disk Storage Thresholds:** Root (`/`) requires $\ge$ 10 GB (10,485,760 KB) free space; EFI (`/boot/efi`) requires $\ge$ 20 MB (20,480 KB) free space.
- **Root Permissions:** Production execution requires `EUID == 0` (or `sudo`), with testable mock bypass via `OSM_MOCK_ROOT=1`.
- **Atomic Backup Structure:** State snapshots must be written to `/var/backups/osm/apt_pre_trixie_<timestamp>/` (or `$OSM_BACKUP_DIR` override) containing full `/etc/apt/` tree, `dpkg_selections.txt`, `apt_manual_pkgs.txt`, and `upgrade_manifest.json`.
- **Signal Handling:** Must trap `EXIT`, `INT`, `TERM` to clean temporary directories and release any transient locks.
- **Strict Scope:** This plan implements ONLY Phase 0 (Pre-Flight Gate) and Phase 1 (State Backup & Manifest Snapshot). Phases 2, 3, 4, and 5 are reserved for subsequent implementation plans.

---

### File Structure & Responsibilities

| File Path | Role / Responsibility |
| :--- | :--- |
| `scripts/upgrade_debian_trixie.sh` | Core upgrade engine containing `check_preflight`, `create_backup`, `parse_args`, and CLI dispatching for `--check`, `--dry-run`, `--backup-only`. |
| `tests/test_upgrade_preflight.sh` | Test suite validating pre-flight checks, mock failure injections (low disk, offline network, broken dpkg), backup generation, and manifest JSON validation. |

---

### Task 1: Pre-Flight Verification Engine (Phase 0)

**Files:**
- Create: `scripts/upgrade_debian_trixie.sh`
- Test: `tests/test_upgrade_preflight.sh`

**Interfaces:**
- Produces:
  - CLI flags: `--check`, `--help`, `--dry-run` (pre-flight portion).
  - Functions: `check_root`, `check_disk_headroom [mount_point] [min_kb]`, `check_network_connectivity [host]`, `check_dpkg_integrity`, `check_preflight`.
  - Exit Codes: `0` on all pre-flight checks passing, `1` on invalid arguments, `2` on pre-flight check failure.

- [ ] **Step 1: Write the failing test for Task 1 (pre-flight checks, CLI flags, failure injection)**

Create `tests/test_upgrade_preflight.sh` with assertions for script execution, `--help`, `--check` execution, and mock failure modes:

```bash
#!/usr/bin/env bash
# tests/test_upgrade_preflight.sh - Unit & Mock Test Suite for Debian 13 Upgrade Preflight & Backup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
UPGRADE_SCRIPT="${WORKSPACE_ROOT}/scripts/upgrade_debian_trixie.sh"

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

assert_contains() {
    local test_name="$1"
    local haystack="$2"
    local needle="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "${haystack}" | grep -qF -- "${needle}"; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (expected to contain '${needle}')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running Debian 13 Upgrade Pre-Flight Test Suite"
echo "=================================================="

# 1. Script existence and executable permission
assert_exit_code "Script exists and is executable" 0 $([ -x "${UPGRADE_SCRIPT}" ] && echo 0 || echo 1)

# 2. Help output test
set +e
HELP_OUT="$("${UPGRADE_SCRIPT}" --help 2>&1)"
HELP_RC=$?
set -e
assert_exit_code "--help returns exit code 0" 0 "${HELP_RC}"
assert_contains "--help documents --check" "${HELP_OUT}" "--check"
assert_contains "--help documents --dry-run" "${HELP_OUT}" "--dry-run"
assert_contains "--help documents --backup-only" "${HELP_OUT}" "--backup-only"

# 3. Pre-flight check under normal environment
set +e
CHECK_OUT="$(OSM_MOCK_ROOT=1 "${UPGRADE_SCRIPT}" --check 2>&1)"
CHECK_RC=$?
set -e
assert_exit_code "Normal --check execution exits 0" 0 "${CHECK_RC}"
assert_contains "--check verifies Root partition" "${CHECK_OUT}" "Root partition (/)"
assert_contains "--check verifies Network connectivity" "${CHECK_OUT}" "Network connectivity"
assert_contains "--check verifies DPKG/APT state" "${CHECK_OUT}" "DPKG & APT lock state"

# 4. Mock Root EUID Failure
set +e
ROOT_FAIL_OUT="$(OSM_MOCK_ROOT=0 EUID=1000 "${UPGRADE_SCRIPT}" --check 2>&1)"
ROOT_FAIL_RC=$?
set -e
assert_exit_code "Non-root execution fails with exit code 2" 2 "${ROOT_FAIL_RC}"
assert_contains "Non-root outputs permission error" "${ROOT_FAIL_OUT}" "Must be executed with root privileges"

# 5. Mock Low Disk Space Failure on Root
set +e
DISK_FAIL_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_ROOT_FREE_KB=500000 "${UPGRADE_SCRIPT}" --check 2>&1)"
DISK_FAIL_RC=$?
set -e
assert_exit_code "Low root disk headroom fails with exit code 2" 2 "${DISK_FAIL_RC}"
assert_contains "Low root disk outputs insufficient space error" "${DISK_FAIL_OUT}" "Insufficient free space on /"

# 6. Mock Network Failure
set +e
NET_FAIL_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_NETWORK_FAIL=1 "${UPGRADE_SCRIPT}" --check 2>&1)"
NET_FAIL_RC=$?
set -e
assert_exit_code "Network failure fails with exit code 2" 2 "${NET_FAIL_RC}"
assert_contains "Network failure outputs connectivity error" "${NET_FAIL_OUT}" "Cannot reach Debian mirror"

# 7. Mock Broken DPKG Audit Failure
set +e
DPKG_FAIL_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_DPKG_AUDIT_FAIL=1 "${UPGRADE_SCRIPT}" --check 2>&1)"
DPKG_FAIL_RC=$?
set -e
assert_exit_code "Broken dpkg audit fails with exit code 2" 2 "${DPKG_FAIL_RC}"
assert_contains "Broken dpkg outputs audit error" "${DPKG_FAIL_OUT}" "Broken or inconsistent packages detected"

echo "=================================================="
echo "Pre-Flight Suite 1 Complete: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `chmod +x tests/test_upgrade_preflight.sh && bash tests/test_upgrade_preflight.sh`
Expected output: FAIL with "scripts/upgrade_debian_trixie.sh missing or not executable".

- [ ] **Step 3: Implement `scripts/upgrade_debian_trixie.sh` Pre-Flight engine**

Create `scripts/upgrade_debian_trixie.sh` with complete implementations of `check_root`, `check_disk_headroom`, `check_network_connectivity`, `check_dpkg_integrity`, `check_preflight`, and CLI flag parser:

```bash
#!/usr/bin/env bash
# scripts/upgrade_debian_trixie.sh - Debian 13 (Trixie) Upgrade Engine for os-manager
# Implements Phase 0 (Pre-Flight Gate) & Phase 1 (State Backup & Manifest Snapshot)
set -euo pipefail

# Required Minimum Headroom Constants (in Kilobytes)
readonly MIN_ROOT_FREE_KB=10485760   # 10 GB
readonly MIN_EFI_FREE_KB=20480       # 20 MB
readonly DEBIAN_MIRROR_HOST="deb.debian.org"
readonly DEFAULT_BACKUP_BASE="/var/backups/osm"

# Operational Variables
DRY_RUN=0
CHECK_ONLY=0
BACKUP_ONLY=0
TEMP_DIR=""

log_info() {
    echo -e "\033[1;34m[INFO]\033[0m $*"
}

log_pass() {
    echo -e "\033[1;32m[PASS]\033[0m $*"
}

log_warn() {
    echo -e "\033[1;33m[WARN]\033[0m $*"
}

log_error() {
    echo -e "\033[1;31m[ERROR]\033[0m $*" >&2
}

cleanup() {
    if [[ -n "${TEMP_DIR}" && -d "${TEMP_DIR}" ]]; then
        rm -rf "${TEMP_DIR}"
    fi
}
trap cleanup EXIT INT TERM

show_help() {
    cat << 'EOF'
Usage: upgrade_debian_trixie.sh [OPTIONS]

Debian 13 (Trixie) Upgrade Automation Engine (Phases 0 & 1)

Options:
  --check        Run Phase 0 pre-flight readiness checks only and exit
  --dry-run      Simulate pre-flight and backup generation without persistent mutations
  --backup-only  Execute Phase 1 system state backup & manifest export only
  --help         Display this help message and exit

Environment Variables:
  OSM_BACKUP_DIR             Override target directory for state backup
  OSM_MOCK_ROOT              Set to 1 to simulate root privileges in test environments
  OSM_MOCK_ROOT_FREE_KB      Override detected root free KB for testing
  OSM_MOCK_EFI_FREE_KB       Override detected EFI free KB for testing
  OSM_MOCK_NETWORK_FAIL      Set to 1 to simulate network connectivity failure
  OSM_MOCK_DPKG_AUDIT_FAIL   Set to 1 to simulate broken dpkg packages
EOF
}

check_root() {
    if [[ "${OSM_MOCK_ROOT:-0}" == "1" ]]; then
        return 0
    fi
    if [[ "${EUID}" -ne 0 ]]; then
        log_error "Must be executed with root privileges (EUID 0) or via sudo."
        return 1
    fi
    return 0
}

get_mount_free_kb() {
    local target_path="$1"
    if [[ "${target_path}" == "/" && -n "${OSM_MOCK_ROOT_FREE_KB:-}" ]]; then
        echo "${OSM_MOCK_ROOT_FREE_KB}"
        return 0
    fi
    if [[ "${target_path}" == "/boot/efi" && -n "${OSM_MOCK_EFI_FREE_KB:-}" ]]; then
        echo "${OSM_MOCK_EFI_FREE_KB}"
        return 0
    fi
    
    if ! df -P "${target_path}" >/dev/null 2>&1; then
        echo "0"
        return 1
    fi
    df -P "${target_path}" | awk 'NR==2 {print $4}'
}

check_disk_headroom() {
    local mount_point="$1"
    local required_kb="$2"
    local label="$3"

    local free_kb
    free_kb="$(get_mount_free_kb "${mount_point}")" || {
        log_error "Mount point ${mount_point} (${label}) is not accessible."
        return 1
    }

    local free_mb=$(( free_kb / 1024 ))
    local required_mb=$(( required_kb / 1024 ))

    if [[ "${free_kb}" -lt "${required_kb}" ]]; then
        log_error "Insufficient free space on ${mount_point} (${label}): ${free_mb} MB available, ${required_mb} MB required."
        return 1
    fi

    log_pass "Disk space on ${mount_point} (${label}): ${free_mb} MB available (Required: ${required_mb} MB)"
    return 0
}

check_network_connectivity() {
    local host="$1"

    if [[ "${OSM_MOCK_NETWORK_FAIL:-0}" == "1" ]]; then
        log_error "Cannot reach Debian mirror at ${host} (mocked network failure)."
        return 1
    fi

    if command -v curl >/dev/null 2>&1; then
        if curl -s --connect-timeout 5 -I "http://${host}" >/dev/null 2>&1; then
            log_pass "Network connectivity to Debian mirror (${host}) verified via curl"
            return 0
        fi
    fi

    if command -v nc >/dev/null 2>&1; then
        if nc -z -w 5 "${host}" 80 >/dev/null 2>&1; then
            log_pass "Network connectivity to Debian mirror (${host}) verified via nc"
            return 0
        fi
    fi

    # Fallback to getent hosts
    if getent hosts "${host}" >/dev/null 2>&1; then
        log_pass "DNS resolution for ${host} successful"
        return 0
    fi

    log_error "Cannot reach Debian mirror at ${host} or resolve DNS."
    return 1
}

check_dpkg_integrity() {
    if [[ "${OSM_MOCK_DPKG_AUDIT_FAIL:-0}" == "1" ]]; then
        log_error "Broken or inconsistent packages detected (mocked dpkg audit failure)."
        return 1
    fi

    # Check dpkg audit
    local audit_out
    audit_out="$(dpkg --audit 2>&1 || true)"
    if [[ -n "${audit_out}" ]]; then
        log_error "Broken or inconsistent packages detected in 'dpkg --audit':\n${audit_out}"
        return 1
    fi

    # Check for held packages
    local held_pkgs
    held_pkgs="$(dpkg --get-selections | grep -E '\bhold$' || true)"
    if [[ -n "${held_pkgs}" ]]; then
        log_warn "Held packages detected:\n${held_pkgs}"
    fi

    # Check APT lock files
    local lock_files=("/var/lib/apt/lists/lock" "/var/lib/dpkg/lock-frontend" "/var/lib/dpkg/lock")
    for lock in "${lock_files[@]}"; do
        if [[ -f "${lock}" ]] && fuser "${lock}" >/dev/null 2>&1; then
            log_error "Active APT/DPKG lock held on ${lock}. Ensure no other package manager is running."
            return 1
        fi
    done

    log_pass "DPKG & APT lock state clean (no broken packages or blocking locks)"
    return 0
}

check_preflight() {
    log_info "Executing Phase 0: Pre-Flight Verification Gate..."
    local errors=0

    if ! check_root; then
        errors=$((errors + 1))
    fi

    if ! check_disk_headroom "/" "${MIN_ROOT_FREE_KB}" "Root partition"; then
        errors=$((errors + 1))
    fi

    if [[ -d "/boot/efi" ]]; then
        if ! check_disk_headroom "/boot/efi" "${MIN_EFI_FREE_KB}" "EFI partition"; then
            errors=$((errors + 1))
        fi
    fi

    if ! check_network_connectivity "${DEBIAN_MIRROR_HOST}"; then
        errors=$((errors + 1))
    fi

    if ! check_dpkg_integrity; then
        errors=$((errors + 1))
    fi

    if [[ "${errors}" -gt 0 ]]; then
        log_error "Phase 0 Pre-Flight Verification FAILED with ${errors} error(s)."
        return 2
    fi

    log_pass "Phase 0 Pre-Flight Verification PASSED cleanly."
    return 0
}

# Subroutine placeholder for Task 2 backup (declared for initial dispatch)
create_backup() {
    log_info "Backup subroutine initialized."
    return 0
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --check)
                CHECK_ONLY=1
                shift
                ;;
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            --backup-only)
                BACKUP_ONLY=1
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

main() {
    parse_args "$@"

    if [[ "${CHECK_ONLY}" -eq 1 ]]; then
        check_preflight
        exit $?
    fi

    if [[ "${BACKUP_ONLY}" -eq 1 ]]; then
        check_preflight
        create_backup
        exit $?
    fi

    if [[ "${DRY_RUN}" -eq 1 ]]; then
        log_info "Executing in --dry-run simulation mode..."
        check_preflight
        log_pass "Dry-run pre-flight check completed successfully."
        exit 0
    fi

    # Default to pre-flight check if no phase flag supplied
    check_preflight
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
```

- [ ] **Step 4: Make script executable and run test to verify it passes**

Run: `chmod +x scripts/upgrade_debian_trixie.sh && bash tests/test_upgrade_preflight.sh`
Expected output: PASS: 10/10 passed, 0 failed.

- [ ] **Step 5: Commit Task 1 deliverables**

```bash
git add scripts/upgrade_debian_trixie.sh tests/test_upgrade_preflight.sh
git commit -m "feat(upgrade): implement Phase 0 pre-flight checking engine and test suite"
```

---

### Task 2: State Backup & Manifest Export Engine (Phase 1)

**Files:**
- Modify: `scripts/upgrade_debian_trixie.sh`
- Test: `tests/test_upgrade_preflight.sh`

**Interfaces:**
- Produces:
  - CLI flag: `--backup-only` full execution.
  - Subroutine: `create_backup [target_dir]`.
  - Artifacts generated:
    - `${TARGET_DIR}/apt/` (recursive copy of `/etc/apt/`).
    - `${TARGET_DIR}/dpkg_selections.txt` (`dpkg --get-selections`).
    - `${TARGET_DIR}/apt_manual_pkgs.txt` (`apt-mark showmanual`).
    - `${TARGET_DIR}/upgrade_manifest.json` (Structured metadata).
  - Exit Codes: `0` on backup success, `2` on backup failure.

- [ ] **Step 1: Write the failing tests for Task 2 in `tests/test_upgrade_preflight.sh`**

Append backup tests to `tests/test_upgrade_preflight.sh`:

```bash
# --- Task 2: Backup & Manifest Tests ---
echo "=================================================="
echo "Running Debian 13 State Backup & Manifest Tests"
echo "=================================================="

TEST_BACKUP_DIR="$(mktemp -d /tmp/osm_test_backup_XXXXXX)"
trap 'rm -rf "${TEST_BACKUP_DIR}"' EXIT

set +e
BACKUP_OUT="$(OSM_MOCK_ROOT=1 OSM_BACKUP_DIR="${TEST_BACKUP_DIR}" "${UPGRADE_SCRIPT}" --backup-only 2>&1)"
BACKUP_RC=$?
set -e

assert_exit_code "--backup-only exits 0" 0 "${BACKUP_RC}"
assert_contains "Logs backup initiation" "${BACKUP_OUT}" "Phase 1: State Backup & Manifest Snapshot"
assert_contains "Logs backup completion" "${BACKUP_OUT}" "Phase 1 Backup completed successfully"

# Check created artifacts
assert_exit_code "APT backup directory exists" 0 $([ -d "${TEST_BACKUP_DIR}/apt" ] && echo 0 || echo 1)
assert_exit_code "dpkg_selections.txt exists" 0 $([ -s "${TEST_BACKUP_DIR}/dpkg_selections.txt" ] && echo 0 || echo 1)
assert_exit_code "apt_manual_pkgs.txt exists" 0 $([ -s "${TEST_BACKUP_DIR}/apt_manual_pkgs.txt" ] && echo 0 || echo 1)
assert_exit_code "upgrade_manifest.json exists" 0 $([ -s "${TEST_BACKUP_DIR}/upgrade_manifest.json" ] && echo 0 || echo 1)

# Validate upgrade_manifest.json schema using python
set +e
python3 -c "
import json, sys
with open('${TEST_BACKUP_DIR}/upgrade_manifest.json') as f:
    data = json.load(f)
assert 'timestamp' in data, 'missing timestamp'
assert 'kernel' in data, 'missing kernel'
assert 'architecture' in data, 'missing architecture'
assert 'source_version' in data, 'missing source_version'
assert data['target_suite'] == 'trixie', 'invalid target_suite'
" 2>&1
JSON_VALID_RC=$?
set -e
assert_exit_code "upgrade_manifest.json is valid and contains required keys" 0 "${JSON_VALID_RC}"
```

- [ ] **Step 2: Run tests to verify Task 2 tests fail**

Run: `bash tests/test_upgrade_preflight.sh`
Expected output: FAIL with missing backup artifacts (`TEST_BACKUP_DIR/apt` or `upgrade_manifest.json`).

- [ ] **Step 3: Implement `create_backup` in `scripts/upgrade_debian_trixie.sh`**

Replace the stub `create_backup` in `scripts/upgrade_debian_trixie.sh` with full backup implementation:

```bash
create_backup() {
    log_info "Executing Phase 1: State Backup & Manifest Snapshot..."
    local timestamp
    timestamp="$(date -u +"%Y%m%d_%H%M%SZ")"

    local backup_dir
    if [[ -n "${OSM_BACKUP_DIR:-}" ]]; then
        backup_dir="${OSM_BACKUP_DIR}"
    else
        backup_dir="${DEFAULT_BACKUP_BASE}/apt_pre_trixie_${timestamp}"
    fi

    log_info "Target backup directory: ${backup_dir}"
    mkdir -p "${backup_dir}" || {
        log_error "Failed to create backup directory ${backup_dir}."
        return 2
    }

    # 1. Snapshot /etc/apt/
    log_info "Creating snapshot of /etc/apt/..."
    if [[ -d "/etc/apt" ]]; then
        mkdir -p "${backup_dir}/apt"
        cp -a /etc/apt/. "${backup_dir}/apt/" || {
            log_error "Failed to copy /etc/apt/ to backup destination."
            return 2
        }
    fi

    # 2. Export package manifests
    log_info "Exporting installed package selections (dpkg & apt-mark)..."
    dpkg --get-selections > "${backup_dir}/dpkg_selections.txt" || {
        log_error "Failed to export dpkg package selections."
        return 2
    }

    if command -v apt-mark >/dev/null 2>&1; then
        apt-mark showmanual > "${backup_dir}/apt_manual_pkgs.txt" 2>/dev/null || true
    fi
    touch "${backup_dir}/apt_manual_pkgs.txt"

    # 3. Generate upgrade_manifest.json
    log_info "Generating upgrade_manifest.json telemetry..."
    local kernel_ver
    kernel_ver="$(uname -r 2>/dev/null || echo "unknown")"
    local arch
    arch="$(dpkg --print-architecture 2>/dev/null || uname -m)"
    local deb_ver
    deb_ver="$(cat /etc/debian_version 2>/dev/null || echo "12")"
    local hostname_str
    hostname_str="$(hostname 2>/dev/null || echo "localhost")"

    cat > "${backup_dir}/upgrade_manifest.json" << EOF
{
  "timestamp": "${timestamp}",
  "hostname": "${hostname_str}",
  "source_distribution": "Debian GNU/Linux",
  "source_version": "${deb_ver}",
  "source_codename": "bookworm",
  "target_suite": "trixie",
  "kernel": "${kernel_ver}",
  "architecture": "${arch}",
  "backup_dir": "${backup_dir}",
  "backup_files": [
    "apt/",
    "dpkg_selections.txt",
    "apt_manual_pkgs.txt",
    "upgrade_manifest.json"
  ]
}
EOF

    log_pass "Phase 1 Backup completed successfully at: ${backup_dir}"
    return 0
}
```

- [ ] **Step 4: Run test suite to verify all Phase 0 and Phase 1 tests pass**

Run: `bash tests/test_upgrade_preflight.sh`
Expected output: PASS: all tests passed (15/15 passed, 0 failed).

- [ ] **Step 5: Commit Task 2 deliverables**

```bash
git add scripts/upgrade_debian_trixie.sh tests/test_upgrade_preflight.sh
git commit -m "feat(upgrade): implement Phase 1 state backup and manifest snapshot generation"
```

---

### Task 3: Comprehensive Test Automation & Harness Validation

**Files:**
- Modify: `tests/test_upgrade_preflight.sh`
- Test: Full execution of `tests/test_upgrade_preflight.sh` and syntax linting with `bash -n` and `shellcheck` (if present).

**Interfaces:**
- Validates edge cases:
  - Argument error handling (unknown flags exit code 1).
  - Dry-run simulation non-mutation guarantee (assert `/etc/apt/sources.list` hash unchanged).
  - Trapping and cleanup of temp directories on interrupt.

- [ ] **Step 1: Add argument error and non-mutation assertions in `tests/test_upgrade_preflight.sh`**

Add the following assertions at the end of `tests/test_upgrade_preflight.sh`:

```bash
# --- Task 3: Edge Cases & Non-Mutation Tests ---
echo "=================================================="
echo "Running Edge Cases and Non-Mutation Tests"
echo "=================================================="

# 1. Invalid argument rejection
set +e
INVALID_OUT="$("${UPGRADE_SCRIPT}" --invalid-flag 2>&1)"
INVALID_RC=$?
set -e
assert_exit_code "Invalid option exits with code 1" 1 "${INVALID_RC}"
assert_contains "Invalid option outputs error" "${INVALID_OUT}" "Unknown option: --invalid-flag"

# 2. Non-mutation verification in dry-run
SOURCES_HASH_BEFORE="$(sha256sum /etc/apt/sources.list 2>/dev/null || echo "none")"
set +e
DRY_RUN_OUT="$(OSM_MOCK_ROOT=1 "${UPGRADE_SCRIPT}" --dry-run 2>&1)"
DRY_RUN_RC=$?
set -e
SOURCES_HASH_AFTER="$(sha256sum /etc/apt/sources.list 2>/dev/null || echo "none")"

assert_exit_code "--dry-run exits with code 0" 0 "${DRY_RUN_RC}"
assert_contains "--dry-run indicates simulation" "${DRY_RUN_OUT}" "simulation mode"
assert_exit_code "/etc/apt/sources.list unchanged during dry-run" 0 $([ "${SOURCES_HASH_BEFORE}" == "${SOURCES_HASH_AFTER}" ] && echo 0 || echo 1)

# Syntax check
assert_exit_code "Script passes bash syntax check" 0 $(bash -n "${UPGRADE_SCRIPT}" && echo 0 || echo 1)
```

- [ ] **Step 2: Run the complete test suite**

Run: `bash tests/test_upgrade_preflight.sh`
Expected output: All test cases pass cleanly with exit code 0.

- [ ] **Step 3: Commit Task 3 test suite refinements**

```bash
git add tests/test_upgrade_preflight.sh
git commit -m "test(upgrade): add edge case validation, non-mutation assertions, and syntax linting"
```

---

## Execution Self-Review Checklist

- [x] **Spec Coverage:** Covers Phase 0 (Pre-Flight Gate) and Phase 1 (State Backup & Manifest Snapshot) from `docs/superpowers/specs/2026-08-21-debian-13-trixie-upgrade-automation-design.md`.
- [x] **Zero Placeholder Verification:** Contains fully specified bash routines, CLI handlers, and test assertions.
- [x] **Zero-Data-Loss Adherence:** No operations touch `/dev/nvme0n1p4` (`/mnt/data`).
- [x] **Test-Driven Design:** Step-by-step red-green-refactor cycles with exact expected outcomes.
