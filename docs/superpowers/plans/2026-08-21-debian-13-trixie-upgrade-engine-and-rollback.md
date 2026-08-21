# Debian 13 (Trixie) Upgrade: Engine & Auto-Rollback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 2 (Source Matrix Transition), Phase 3 (Minimal Safe Upgrade), and Phase 4 (Full Distribution Upgrade with Auto-Rollback) in `scripts/upgrade_debian_trixie.sh` with robust dry-run simulation and comprehensive mock tests in `tests/test_upgrade_pipeline.sh`.

**Architecture:** A fail-safe distribution upgrade pipeline that transitions APT repository configurations to Debian 13 (Trixie) preserving `non-free-firmware` across all suites, runs staged two-step upgrades (`--without-new-pkgs` followed by `full-upgrade`) with non-interactive debconf configurations, and executes automatic rollback to pre-upgrade backup snapshots if package synchronization fails.

**Tech Stack:** Bash 4.4+, GNU coreutils (`cp`, `mv`, `sed`, `mktemp`), `apt-get`, `dpkg`, signal traps (`trap cleanup EXIT INT TERM`).

**Spec:** [`docs/superpowers/specs/2026-08-21-debian-13-trixie-upgrade-automation-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-21-debian-13-trixie-upgrade-automation-design.md)

---

## Global Constraints

- **Firmware Protection:** All generated repository templates MUST contain `main`, `contrib`, `non-free`, and `non-free-firmware` across `trixie`, `trixie-updates`, `trixie-security`, and `trixie-backports`.
- **Zero-Data-Loss Guardrail:** No command shall inspect, alter, unmount, or format `/dev/nvme0n1p4` (`/mnt/data`).
- **Debconf Non-Interactive Execution:** Upgrades must run with `DEBIAN_FRONTEND=noninteractive` and DPkg options `-o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"`.
- **Automatic Rollback on Failure:** If `apt-get update` fails after source transition, the script must restore `/etc/apt/` from the Phase 1 backup directory and exit with code `3`.
- **Safety Testing Principle:** No tests shall execute destructive live package operations on the host; tests must use sandbox APT directories (`OSM_APT_DIR`) and mocked execution flags (`OSM_MOCK_APT=1`).
- **Strict Plan Scope:** CLI Click wrappers and post-upgrade hardware diagnostics belong to Plan 3.

---

### File Structure & Responsibilities

| File Path | Role / Responsibility |
| :--- | :--- |
| `scripts/upgrade_debian_trixie.sh` | Extended to implement `generate_trixie_sources`, `transition_sources`, `run_minimal_upgrade`, `run_full_upgrade`, `rollback_apt`, and the full execution pipeline `--apply`. |
| `tests/test_upgrade_pipeline.sh` | Test suite covering repository template generation, source matrix transition, third-party repo disabling, staged upgrade execution, auto-rollback upon update failure, and explicit `--rollback`. |

---

### Task 1: APT Source Matrix Transition Engine (Phase 2)

**Files:**
- Modify: `scripts/upgrade_debian_trixie.sh`
- Test: `tests/test_upgrade_pipeline.sh`

**Interfaces:**
- Produces:
  - Subroutines: `generate_trixie_sources [target_file]`, `transition_sources [apt_base_dir]`.
  - Behavior: Writes Debian 13 repository matrix to `sources.list` including `non-free-firmware`; disables `.list` files in `sources.list.d/` by renaming to `.disabled_for_upgrade`.
  - Override: Uses `${OSM_APT_DIR:-/etc/apt}` to allow sandboxed unit testing without root.

- [ ] **Step 1: Write the failing tests for Task 1 in `tests/test_upgrade_pipeline.sh`**

Create `tests/test_upgrade_pipeline.sh` with assertions for `generate_trixie_sources` and `transition_sources`:

```bash
#!/usr/bin/env bash
# tests/test_upgrade_pipeline.sh - Unit & Pipeline Tests for Debian 13 Upgrade Engine
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
echo "Running Debian 13 Upgrade Pipeline Test Suite"
echo "=================================================="

# 1. Script existence check
assert_exit_code "Upgrade script exists and is executable" 0 $([ -x "${UPGRADE_SCRIPT}" ] && echo 0 || echo 1)

# 2. Test sandbox source matrix transition
SANDBOX_DIR="$(mktemp -d /tmp/osm_sandbox_apt_XXXXXX)"
SANDBOX_BACKUP="$(mktemp -d /tmp/osm_sandbox_backup_XXXXXX)"
trap 'rm -rf "${SANDBOX_DIR}" "${SANDBOX_BACKUP}"' EXIT

mkdir -p "${SANDBOX_DIR}/sources.list.d"
cat > "${SANDBOX_DIR}/sources.list" << 'EOF'
deb http://deb.debian.org/debian bookworm main non-free-firmware
deb http://security.debian.org/debian-security bookworm-security main non-free-firmware
EOF
cat > "${SANDBOX_DIR}/sources.list.d/third_party.list" << 'EOF'
deb [signed-by=/etc/apt/keyrings/test.gpg] https://example.com/debian bookworm main
EOF

# Run internal transition test via sourced function or dry-run execution
set +e
TRANSITION_OUT="$(OSM_MOCK_ROOT=1 OSM_APT_DIR="${SANDBOX_DIR}" OSM_BACKUP_DIR="${SANDBOX_BACKUP}" "${UPGRADE_SCRIPT}" --transition-only 2>&1)"
TRANSITION_RC=$?
set -e

assert_exit_code "--transition-only exits 0" 0 "${TRANSITION_RC}"

# Verify sources.list contains trixie components
SOURCES_CONTENT="$(cat "${SANDBOX_DIR}/sources.list")"
assert_contains "sources.list contains trixie suite" "${SOURCES_CONTENT}" "deb http://deb.debian.org/debian trixie main"
assert_contains "sources.list contains non-free-firmware" "${SOURCES_CONTENT}" "non-free-firmware"
assert_contains "sources.list contains trixie-updates" "${SOURCES_CONTENT}" "trixie-updates"
assert_contains "sources.list contains trixie-security" "${SOURCES_CONTENT}" "trixie-security"
assert_contains "sources.list contains trixie-backports" "${SOURCES_CONTENT}" "trixie-backports"

# Verify third party repo is renamed to disabled
assert_exit_code "Third party repo disabled" 0 $([ -f "${SANDBOX_DIR}/sources.list.d/third_party.list.disabled_for_upgrade" ] && echo 0 || echo 1)
assert_exit_code "Original third party list removed" 0 $([ ! -f "${SANDBOX_DIR}/sources.list.d/third_party.list" ] && echo 0 || echo 1)

echo "=================================================="
echo "Task 1 Tests Complete: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `chmod +x tests/test_upgrade_pipeline.sh && bash tests/test_upgrade_pipeline.sh`
Expected output: FAIL with "Unknown option: --transition-only".

- [ ] **Step 3: Implement `generate_trixie_sources` and `transition_sources` in `scripts/upgrade_debian_trixie.sh`**

Add the transition subroutines to `scripts/upgrade_debian_trixie.sh`:

```bash
generate_trixie_sources() {
    local target_file="$1"
    log_info "Writing Debian 13 (Trixie) source matrix to ${target_file}..."

    cat > "${target_file}" << 'EOF'
# Debian 13 (Trixie) Core Repositories - Generated by os-manager
deb http://deb.debian.org/debian trixie main contrib non-free non-free-firmware
deb-src http://deb.debian.org/debian trixie main contrib non-free non-free-firmware

# Debian 13 (Trixie) Updates
deb http://deb.debian.org/debian trixie-updates main contrib non-free non-free-firmware
deb-src http://deb.debian.org/debian trixie-updates main contrib non-free non-free-firmware

# Debian 13 (Trixie) Security Updates
deb http://security.debian.org/debian-security/ trixie-security main contrib non-free non-free-firmware
deb-src http://security.debian.org/debian-security/ trixie-security main contrib non-free non-free-firmware

# Debian 13 (Trixie) Backports
deb http://deb.debian.org/debian trixie-backports main contrib non-free non-free-firmware
deb-src http://deb.debian.org/debian trixie-backports main contrib non-free non-free-firmware
EOF
}

transition_sources() {
    local apt_dir="${OSM_APT_DIR:-/etc/apt}"
    log_info "Executing Phase 2: APT Source Matrix Transition in ${apt_dir}..."

    if [[ ! -d "${apt_dir}" ]]; then
        log_error "Target APT directory ${apt_dir} does not exist."
        return 2
    fi

    # 1. Generate new trixie sources.list
    generate_trixie_sources "${apt_dir}/sources.list"

    # 2. Temporarily disable active third-party repository lists in sources.list.d
    if [[ -d "${apt_dir}/sources.list.d" ]]; then
        shopt -s nullglob
        local list_files=("${apt_dir}/sources.list.d/"*.list)
        shopt -u nullglob

        for f in "${list_files[@]}"; do
            log_warn "Disabling third-party repository during upgrade: $(basename "${f}")"
            mv "${f}" "${f}.disabled_for_upgrade"
        done
    fi

    log_pass "Phase 2 Source Matrix Transition completed successfully."
    return 0
}
```

Update `parse_args` to support `--transition-only`:

```bash
        --transition-only)
            TRANSITION_ONLY=1
            shift
            ;;
```

And in `main`:

```bash
    if [[ "${TRANSITION_ONLY:-0}" -eq 1 ]]; then
        transition_sources
        exit $?
    fi
```

- [ ] **Step 4: Run test to verify Task 1 passes**

Run: `bash tests/test_upgrade_pipeline.sh`
Expected output: PASS: 8/8 passed, 0 failed.

- [ ] **Step 5: Commit Task 1 deliverables**

```bash
git add scripts/upgrade_debian_trixie.sh tests/test_upgrade_pipeline.sh
git commit -m "feat(upgrade): implement Phase 2 APT source matrix transition and repository templating"
```

---

### Task 2: Staged Upgrade Engine & Automated Fallback Rollback (Phases 3 & 4)

**Files:**
- Modify: `scripts/upgrade_debian_trixie.sh`
- Test: `tests/test_upgrade_pipeline.sh`

**Interfaces:**
- Produces:
  - CLI flags: `--apply`, `--rollback [backup_dir]`.
  - Subroutines:
    - `run_minimal_upgrade`: Phase 3 safe upgrade (`--without-new-pkgs`).
    - `run_full_upgrade`: Phase 4 full upgrade (`full-upgrade`).
    - `rollback_apt [backup_dir]`: Restores APT configuration and runs recovery `apt-get update`.
    - `run_pipeline`: Full end-to-end execution of Phases 0 $\rightarrow$ 4 with auto-rollback on failure.
  - Exit Codes: `0` on success, `2` on preflight/backup failure, `3` on update/upgrade failure (with rollback executed).

- [ ] **Step 1: Write failing tests for Task 2 (mocked staged upgrades, auto-rollback on update failure, explicit rollback)**

Append Task 2 test cases to `tests/test_upgrade_pipeline.sh`:

```bash
# --- Task 2: Staged Upgrade & Auto-Rollback Tests ---
echo "=================================================="
echo "Running Staged Upgrade & Rollback Tests"
echo "=================================================="

# 1. Test Mocked Full Pipeline Execution (--apply)
set +e
APPLY_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_APT=1 OSM_APT_DIR="${SANDBOX_DIR}" OSM_BACKUP_DIR="${SANDBOX_BACKUP}" "${UPGRADE_SCRIPT}" --apply 2>&1)"
APPLY_RC=$?
set -e

assert_exit_code "Mocked --apply pipeline exits 0" 0 "${APPLY_RC}"
assert_contains "Executes Phase 0 Preflight" "${APPLY_OUT}" "Phase 0: Pre-Flight Verification Gate"
assert_contains "Executes Phase 1 Backup" "${APPLY_OUT}" "Phase 1: State Backup"
assert_contains "Executes Phase 2 Transition" "${APPLY_OUT}" "Phase 2: APT Source Matrix Transition"
assert_contains "Executes Phase 3 Minimal Upgrade" "${APPLY_OUT}" "Phase 3: Minimal Safe Upgrade"
assert_contains "Executes Phase 4 Full Upgrade" "${APPLY_OUT}" "Phase 4: Full Distribution Upgrade"

# 2. Test Auto-Rollback upon APT Update Failure
SANDBOX_FAIL_DIR="$(mktemp -d /tmp/osm_sandbox_fail_apt_XXXXXX)"
SANDBOX_FAIL_BACKUP="$(mktemp -d /tmp/osm_sandbox_fail_backup_XXXXXX)"
trap 'rm -rf "${SANDBOX_DIR}" "${SANDBOX_BACKUP}" "${SANDBOX_FAIL_DIR}" "${SANDBOX_FAIL_BACKUP}"' EXIT

mkdir -p "${SANDBOX_FAIL_DIR}/sources.list.d"
cat > "${SANDBOX_FAIL_DIR}/sources.list" << 'EOF'
deb http://deb.debian.org/debian bookworm main non-free-firmware
EOF
cat > "${SANDBOX_FAIL_DIR}/sources.list.d/custom.list" << 'EOF'
deb http://example.com/deb custom main
EOF

set +e
FAIL_APPLY_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_APT=1 OSM_MOCK_APT_UPDATE_FAIL=1 OSM_APT_DIR="${SANDBOX_FAIL_DIR}" OSM_BACKUP_DIR="${SANDBOX_FAIL_BACKUP}" "${UPGRADE_SCRIPT}" --apply 2>&1)"
FAIL_APPLY_RC=$?
set -e

assert_exit_code "Pipeline with failed apt update exits 3" 3 "${FAIL_APPLY_RC}"
assert_contains "Auto-rollback is triggered" "${FAIL_APPLY_OUT}" "Triggering automatic rollback of APT configuration"
assert_contains "Auto-rollback logs restoration" "${FAIL_APPLY_OUT}" "Restoring APT configuration from backup"

# Verify rollback restored original Bookworm sources.list and enabled custom.list
RESTORED_SOURCES="$(cat "${SANDBOX_FAIL_DIR}/sources.list")"
assert_contains "Restored sources contains bookworm" "${RESTORED_SOURCES}" "bookworm"
assert_exit_code "Restored third-party list restored" 0 $([ -f "${SANDBOX_FAIL_DIR}/sources.list.d/custom.list" ] && echo 0 || echo 1)

# 3. Test Explicit Manual Rollback (--rollback)
set +e
MANUAL_ROLLBACK_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_APT=1 OSM_APT_DIR="${SANDBOX_DIR}" "${UPGRADE_SCRIPT}" --rollback "${SANDBOX_BACKUP}" 2>&1)"
MANUAL_ROLLBACK_RC=$?
set -e

assert_exit_code "Explicit --rollback exits 0" 0 "${MANUAL_ROLLBACK_RC}"
assert_contains "Explicit rollback logs success" "${MANUAL_ROLLBACK_OUT}" "APT rollback completed successfully"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test_upgrade_pipeline.sh`
Expected output: FAIL with "Unknown option: --apply".

- [ ] **Step 3: Implement Staged Upgrade Subroutines & Auto-Rollback Engine**

In `scripts/upgrade_debian_trixie.sh`, implement:

```bash
run_apt_cmd() {
    local cmd=("$@")
    if [[ "${OSM_MOCK_APT:-0}" == "1" ]]; then
        log_info "[MOCK APT] Executing: ${cmd[*]}"
        if [[ "${OSM_MOCK_APT_UPDATE_FAIL:-0}" == "1" && "${cmd[0]}" == "apt-get" && "${cmd[1]}" == "update" ]]; then
            log_error "[MOCK APT] Simulated apt-get update failure."
            return 100
        fi
        return 0
    fi

    DEBIAN_FRONTEND=noninteractive "${cmd[@]}"
}

rollback_apt() {
    local backup_dir="$1"
    local apt_dir="${OSM_APT_DIR:-/etc/apt}"

    log_warn "Restoring APT configuration from backup: ${backup_dir}/apt -> ${apt_dir}..."

    if [[ ! -d "${backup_dir}/apt" ]]; then
        log_error "Backup APT directory ${backup_dir}/apt not found. Cannot rollback."
        return 1
    fi

    # Re-enable any disabled third-party repositories
    rm -rf "${apt_dir:?}"/*
    cp -a "${backup_dir}/apt/." "${apt_dir}/"

    log_info "Synchronizing package lists following rollback..."
    run_apt_cmd apt-get update || true

    log_pass "APT rollback completed successfully."
    return 0
}

run_minimal_upgrade() {
    log_info "Executing Phase 3: Minimal Safe Upgrade (--without-new-pkgs)..."

    log_info "Synchronizing Debian 13 package lists..."
    if ! run_apt_cmd apt-get update; then
        log_error "Failed to synchronize Debian 13 package lists."
        return 1
    fi

    log_info "Running staged minimal upgrade..."
    if ! run_apt_cmd apt-get upgrade --without-new-pkgs -y \
        -o Dpkg::Options::="--force-confdef" \
        -o Dpkg::Options::="--force-confold"; then
        log_error "Minimal safe upgrade encountered an error."
        return 1
    fi

    log_pass "Phase 3 Minimal Safe Upgrade completed successfully."
    return 0
}

run_full_upgrade() {
    log_info "Executing Phase 4: Full Distribution Upgrade (full-upgrade)..."

    log_info "Running apt-get full-upgrade..."
    if ! run_apt_cmd apt-get full-upgrade -y \
        -o Dpkg::Options::="--force-confdef" \
        -o Dpkg::Options::="--force-confold"; then
        log_error "Full distribution upgrade encountered an error."
        return 1
    fi

    log_info "Cleaning obsolete orphaned packages..."
    run_apt_cmd apt-get autoremove --purge -y || true
    run_apt_cmd apt-get clean || true

    log_pass "Phase 4 Full Distribution Upgrade completed successfully."
    return 0
}

run_pipeline() {
    log_info "Starting Automated Debian 13 (Trixie) Upgrade Pipeline..."

    # Phase 0: Pre-Flight Gate
    if ! check_preflight; then
        log_error "Aborting upgrade: Pre-Flight checks failed."
        return 2
    fi

    # Phase 1: State Backup
    local current_backup_dir
    local timestamp
    timestamp="$(date -u +"%Y%m%d_%H%M%SZ")"
    current_backup_dir="${OSM_BACKUP_DIR:-${DEFAULT_BACKUP_BASE}/apt_pre_trixie_${timestamp}}"
    export OSM_BACKUP_DIR="${current_backup_dir}"

    if ! create_backup; then
        log_error "Aborting upgrade: State backup failed."
        return 2
    fi

    # Phase 2: Source Transition
    if ! transition_sources; then
        log_error "Phase 2 source transition failed. Triggering automatic rollback..."
        rollback_apt "${current_backup_dir}"
        return 3
    fi

    # Phase 3: Minimal Safe Upgrade
    if ! run_minimal_upgrade; then
        log_error "Phase 3 minimal upgrade failed! Triggering automatic rollback of APT configuration..."
        rollback_apt "${current_backup_dir}"
        return 3
    fi

    # Phase 4: Full Distribution Upgrade
    if ! run_full_upgrade; then
        log_error "Phase 4 full-upgrade failed! Reverting APT sources..."
        rollback_apt "${current_backup_dir}"
        return 3
    fi

    log_pass "============================================================"
    log_pass "Debian 13 (Trixie) Upgrade Pipeline COMPLETED SUCCESSFULLY!"
    log_pass "Please reboot the system ('sudo reboot') to initialize the new kernel."
    log_pass "============================================================"
    return 0
}
```

Update `parse_args` and `main` to handle `--apply` and `--rollback [dir]`:

```bash
        --apply)
            APPLY_PIPELINE=1
            shift
            ;;
        --rollback)
            ROLLBACK_MODE=1
            shift
            if [[ $# -gt 0 && ! "$1" =~ ^-- ]]; then
                ROLLBACK_DIR="$1"
                shift
            fi
            ;;
```

And in `main`:

```bash
    if [[ "${ROLLBACK_MODE:-0}" -eq 1 ]]; then
        local target_rb="${ROLLBACK_DIR:-}"
        if [[ -z "${target_rb}" ]]; then
            # Find latest backup in DEFAULT_BACKUP_BASE
            target_rb="$(ls -td "${DEFAULT_BACKUP_BASE}"/apt_pre_trixie_* 2>/dev/null | head -n 1 || true)"
        fi
        if [[ -z "${target_rb}" || ! -d "${target_rb}" ]]; then
            log_error "No valid backup directory found for rollback."
            exit 1
        fi
        rollback_apt "${target_rb}"
        exit $?
    fi

    if [[ "${APPLY_PIPELINE:-0}" -eq 1 ]]; then
        run_pipeline
        exit $?
    fi
```

- [ ] **Step 4: Run test to verify all Task 1 and Task 2 tests pass**

Run: `bash tests/test_upgrade_pipeline.sh`
Expected output: PASS: 18/18 passed, 0 failed.

- [ ] **Step 5: Commit Task 2 deliverables**

```bash
git add scripts/upgrade_debian_trixie.sh tests/test_upgrade_pipeline.sh
git commit -m "feat(upgrade): implement Phase 3 minimal upgrade, Phase 4 full upgrade, and automated rollback fallback"
```

---

### Task 3: Comprehensive Pipeline Simulation & Regression Test Suite

**Files:**
- Modify: `tests/test_upgrade_pipeline.sh`
- Test: Full execution of `tests/test_upgrade_pipeline.sh` and `tests/test_upgrade_preflight.sh`.

**Interfaces:**
- Validates:
  - Complete integration of all CLI flags (`--check`, `--dry-run`, `--backup-only`, `--transition-only`, `--apply`, `--rollback`).
  - Signal trapping and clean sandbox teardown.
  - Bash syntax and shellcheck compliance.

- [ ] **Step 1: Add end-to-end integration and dry-run assertions to `tests/test_upgrade_pipeline.sh`**

Append final integration tests to `tests/test_upgrade_pipeline.sh`:

```bash
# --- Task 3: Full End-to-End Dry-Run & Syntax Assertions ---
echo "=================================================="
echo "Running End-to-End Dry-Run & Syntax Checks"
echo "=================================================="

# 1. Full dry-run execution
set +e
FULL_DRY_OUT="$(OSM_MOCK_ROOT=1 "${UPGRADE_SCRIPT}" --dry-run 2>&1)"
FULL_DRY_RC=$?
set -e

assert_exit_code "Full --dry-run exits 0" 0 "${FULL_DRY_RC}"
assert_contains "--dry-run contains preflight pass" "${FULL_DRY_OUT}" "Phase 0 Pre-Flight Verification PASSED"

# 2. Syntax validation
assert_exit_code "Upgrade script syntax valid" 0 $(bash -n "${UPGRADE_SCRIPT}" && echo 0 || echo 1)
assert_exit_code "Pipeline test syntax valid" 0 $(bash -n "${WORKSPACE_ROOT}/tests/test_upgrade_pipeline.sh" && echo 0 || echo 1)
assert_exit_code "Preflight test syntax valid" 0 $(bash -n "${WORKSPACE_ROOT}/tests/test_upgrade_preflight.sh" && echo 0 || echo 1)

echo "=================================================="
echo "Pipeline Test Suite Complete: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0
```

- [ ] **Step 2: Run both test suites to verify full green state**

Run:
```bash
bash tests/test_upgrade_preflight.sh
bash tests/test_upgrade_pipeline.sh
```
Expected output: Both test suites pass 100% with exit code 0.

- [ ] **Step 3: Commit Task 3 regression tests**

```bash
git add tests/test_upgrade_pipeline.sh tests/test_upgrade_preflight.sh
git commit -m "test(upgrade): complete Debian 13 upgrade pipeline regression test suite"
```

---

## Execution Self-Review Checklist

- [x] **Spec Coverage:** Covers Phase 2 (Source Matrix Transition), Phase 3 (Minimal Safe Upgrade), and Phase 4 (Full Distribution Upgrade with Auto-Rollback).
- [x] **Firmware Retention:** `non-free-firmware` component is explicitly included in generated sources across all 4 suites.
- [x] **Zero Placeholder Verification:** Contains complete, runnable implementations of all functions, traps, and tests.
- [x] **Zero-Data-Loss Adherence:** No operations touch `/dev/nvme0n1p4` (`/mnt/data`).
- [x] **Test Isolation:** Enforces mocked/sandboxed execution without modifying host packages during automated tests.
