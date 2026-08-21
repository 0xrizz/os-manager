# Debian 13 (Trixie) Upgrade: deb822 Transition, SOF Firmware & Staged Upgrade Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 2 (deb822 Repository Matrix Transition), Point-of-No-Return Safety Gate, Phase 3 (Minimal Safe Upgrade with intermediate `apt-get clean` and `APT::Keep-Downloaded-Packages="false"`), and Phase 4 (Full Distribution Upgrade with Intel SOF audio firmware `firmware-sof-signed`, `alsa-ucm-conf`, `firmware-misc-nonfree`, `needrestart` suppression, NetworkManager keyfile permission re-enforcement, and offline chroot/host emergency repair) in `scripts/upgrade_debian_trixie.sh` with sandbox pipeline tests in `tests/test_upgrade_pipeline.sh`.

**Architecture:** A zero-dependency POSIX Bash engine transitioning APT to Debian 13's standardized deb822 stanza format (`/etc/apt/sources.list.d/debian.sources`) with `non-free-firmware` guaranteed across all suites, disabling legacy lists, enforcing non-interactive debconf and `needrestart` suppression flags, streaming package downloads without disk retention (`APT::Keep-Downloaded-Packages="false"`), cleaning cache between stages, explicitly installing required Ice Lake sound and wireless drivers, re-verifying NetworkManager permissions, and providing automated `dpkg --configure -a` / `apt-get install -f` emergency recovery in place of unsupported source downgrades.

**Tech Stack:** Bash 4.4+, GNU coreutils (`cp`, `mv`, `sed`, `mktemp`, `tar`), `apt-get`, `dpkg`, deb822 format specification, debconf.

**Spec:** [`docs/superpowers/specs/2026-08-21-debian-13-trixie-upgrade-automation-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-21-debian-13-trixie-upgrade-automation-design.md)

---

## Global Constraints

- **deb822 Standard Format:** Target repository configuration must be written to `${OSM_APT_DIR:-/etc/apt}/sources.list.d/debian.sources` with separate stanzas for core/updates/backports and security.
- **Mandatory Firmware:** Every deb822 stanza MUST include `main`, `contrib`, `non-free`, and `non-free-firmware`.
- **Intel Ice Lake Audio Guarantee:** Phase 4 MUST explicitly install `firmware-sof-signed`, `alsa-ucm-conf`, `firmware-iwlwifi`, and `firmware-misc-nonfree` to guarantee hardware audio and wireless support on Linux 6.12+.
- **Package Archive Streaming & Cache Hygiene:** Pass `-o APT::Keep-Downloaded-Packages="false"` during all upgrade commands and execute intermediate `apt-get clean` immediately following Phase 3 minimal upgrade to prevent storage exhaustion on `/`.
- **Needrestart & Debconf Non-Interactive Configuration:** Execute with `NEEDRESTART_MODE=a`, `NEEDRESTART_SUSPEND=1`, `DEBIAN_FRONTEND=noninteractive`, `DEBIAN_PRIORITY=critical`, `UCF_FORCE_CONFFOLD=1`, and DPkg options `-o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold"`.
- **Legacy Deduplication:** Legacy `${OSM_APT_DIR:-/etc/apt}/sources.list` must be cleared with a header comment to eliminate duplicate target warnings.
- **Zero-Downgrade Invariant:** No automated rollback of APT sources once package unpacking begins. If an upgrade step fails, trigger `dpkg --configure -a` and `apt-get install -f -y` emergency repair.
- **NetworkManager Keyfile Re-Sanitization:** Enforce `0600` permissions on `/etc/NetworkManager/system-connections/*` post-unpack.
- **Sandbox Testing:** Automated tests must run within sandboxed directories (`OSM_APT_DIR`) and mocked execution flags (`OSM_MOCK_APT=1`).

---

### File Structure & Responsibilities

| File Path | Role / Responsibility |
| :--- | :--- |
| `scripts/upgrade_debian_trixie.sh` | Extended to implement `generate_deb822_sources`, `transition_sources`, `confirm_point_of_no_return`, `run_minimal_upgrade`, `install_core_firmware`, `run_full_upgrade`, `emergency_repair_dpkg`, and `--apply`. |
| `tests/test_upgrade_pipeline.sh` | Sandbox pipeline test suite verifying deb822 template generation, legacy deduplication, staged execution, intermediate cache purges, firmware installation queuing, and emergency repair triggers. |

---

### Task 1: deb822 Repository Matrix Transition Engine (Phase 2)

**Files:**
- Modify: `scripts/upgrade_debian_trixie.sh`
- Test: `tests/test_upgrade_pipeline.sh`

**Interfaces:**
- Produces:
  - Subroutines: `generate_deb822_sources [target_file]`, `transition_sources [apt_base_dir]`.
  - Behavior: Generates `sources.list.d/debian.sources`, cleans legacy `sources.list`, and disables third-party lists (`*.disabled_for_upgrade`).
  - CLI flag: `--transition-only`.

- [ ] **Step 1: Write the failing test for Task 1 in `tests/test_upgrade_pipeline.sh`**

Create `tests/test_upgrade_pipeline.sh`:

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
echo "Running Debian 13 deb822 Transition & Pipeline Tests"
echo "=================================================="

# 1. Script check
assert_exit_code "Upgrade script is executable" 0 $([ -x "${UPGRADE_SCRIPT}" ] && echo 0 || echo 1)

# 2. Test sandbox deb822 transition
SANDBOX_DIR="$(mktemp -d /tmp/osm_sandbox_apt_XXXXXX)"
SANDBOX_BACKUP="$(mktemp -d /tmp/osm_sandbox_backup_XXXXXX)"
trap 'rm -rf "${SANDBOX_DIR}" "${SANDBOX_BACKUP}"' EXIT

mkdir -p "${SANDBOX_DIR}/sources.list.d"
echo "deb http://deb.debian.org/debian bookworm main" > "${SANDBOX_DIR}/sources.list"
echo "deb https://example.com/deb bookworm main" > "${SANDBOX_DIR}/sources.list.d/external.list"

set +e
TRANSITION_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_APT_DIR="${SANDBOX_DIR}" OSM_BACKUP_DIR="${SANDBOX_BACKUP}" "${UPGRADE_SCRIPT}" --transition-only 2>&1)"
TRANSITION_RC=$?
set -e

assert_exit_code "--transition-only exits 0" 0 "${TRANSITION_RC}"

# Verify debian.sources created with deb822 format
DEB_SOURCES="${SANDBOX_DIR}/sources.list.d/debian.sources"
assert_exit_code "debian.sources exists" 0 $([ -f "${DEB_SOURCES}" ] && echo 0 || echo 1)

DEB_CONTENT="$(cat "${DEB_SOURCES}")"
assert_contains "deb822 Types stanza" "${DEB_CONTENT}" "Types: deb deb-src"
assert_contains "deb822 URIs stanza" "${DEB_CONTENT}" "URIs: http://deb.debian.org/debian"
assert_contains "deb822 Suites trixie" "${DEB_CONTENT}" "Suites: trixie trixie-updates trixie-backports"
assert_contains "deb822 Components non-free-firmware" "${DEB_CONTENT}" "Components: main contrib non-free non-free-firmware"
assert_contains "deb822 Security URI" "${DEB_CONTENT}" "URIs: http://security.debian.org/debian-security"
assert_contains "deb822 Security Suite" "${DEB_CONTENT}" "Suites: trixie-security"

# Verify legacy sources.list is emptied or deduplicated
LEGACY_CONTENT="$(cat "${SANDBOX_DIR}/sources.list" 2>/dev/null || true)"
assert_exit_code "Legacy sources.list has zero active lines" 0 $([ -z "${LEGACY_CONTENT//[#[:space:]]/}" ] && echo 0 || echo 1)

# Verify third-party repo is disabled
assert_exit_code "External list renamed to disabled" 0 $([ -f "${SANDBOX_DIR}/sources.list.d/external.list.disabled_for_upgrade" ] && echo 0 || echo 1)

echo "=================================================="
echo "Task 1 Tests: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `chmod +x tests/test_upgrade_pipeline.sh && bash tests/test_upgrade_pipeline.sh`
Expected output: FAIL with "Unknown option: --transition-only".

- [ ] **Step 3: Implement deb822 Subroutines in `scripts/upgrade_debian_trixie.sh`**

Add `generate_deb822_sources` and `transition_sources` to `scripts/upgrade_debian_trixie.sh`:

```bash
generate_deb822_sources() {
    local target_file="$1"
    log_info "Writing Debian 13 (Trixie) deb822 repository matrix to ${target_file}..."

    cat > "${target_file}" << 'EOF'
Types: deb deb-src
URIs: http://deb.debian.org/debian
Suites: trixie trixie-updates trixie-backports
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg

Types: deb deb-src
URIs: http://security.debian.org/debian-security
Suites: trixie-security
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
EOF
}

transition_sources() {
    local apt_dir="${OSM_APT_DIR:-/etc/apt}"
    log_info "Executing Phase 2: APT deb822 Repository Matrix Transition in ${apt_dir}..."

    if [[ ! -d "${apt_dir}" ]]; then
        log_error "Target APT directory ${apt_dir} does not exist."
        return 2
    fi

    mkdir -p "${apt_dir}/sources.list.d"

    # 1. Write deb822 format sources
    generate_deb822_sources "${apt_dir}/sources.list.d/debian.sources"

    # 2. Clear legacy sources.list to prevent duplicate warnings
    if [[ -f "${apt_dir}/sources.list" ]]; then
        cat > "${apt_dir}/sources.list" << 'EOF'
# Legacy sources.list cleared by os-manager. Active repositories are configured in sources.list.d/debian.sources
EOF
    fi

    # 3. Disable external third party lists
    shopt -s nullglob
    local list_files=("${apt_dir}/sources.list.d/"*.list)
    shopt -u nullglob

    for f in "${list_files[@]}"; do
        log_warn "Disabling third-party repository during upgrade: $(basename "${f}")"
        mv "${f}" "${f}.disabled_for_upgrade"
    done

    log_pass "Phase 2 deb822 Source Transition completed successfully."
    return 0
}
```

Update `parse_args` to support `--transition-only` and route in `main`.

- [ ] **Step 4: Run test to verify Task 1 passes**

Run: `bash tests/test_upgrade_pipeline.sh`
Expected output: PASS: 10/10 passed, 0 failed.

- [ ] **Step 5: Commit Task 1 deliverables**

```bash
git add scripts/upgrade_debian_trixie.sh tests/test_upgrade_pipeline.sh
git commit -m "feat(upgrade): implement Phase 2 deb822 repository transition with non-free-firmware"
```

---

### Task 2: Staged Upgrade Engine, Intel SOF Audio Firmware & Immediate Cache Purge (Phases 3 & 4)

**Files:**
- Modify: `scripts/upgrade_debian_trixie.sh`
- Test: `tests/test_upgrade_pipeline.sh`

**Interfaces:**
- Produces:
  - Subroutines:
    - `confirm_point_of_no_return`
    - `run_minimal_upgrade`
    - `install_core_firmware`
    - `run_full_upgrade`
    - `emergency_repair_dpkg`
    - `run_pipeline`
  - CLI flags: `--apply`, `--non-interactive`.
  - Behavior: Sets `NEEDRESTART_MODE=a`, `NEEDRESTART_SUSPEND=1`, `UCF_FORCE_CONFFOLD=1`, passes `-o APT::Keep-Downloaded-Packages="false"`, runs minimal upgrade, cleans cache immediately, installs `firmware-sof-signed`, `firmware-iwlwifi`, `firmware-misc-nonfree`, and `alsa-ucm-conf`, runs full upgrade, re-sanitizes NetworkManager keyfile permissions, and triggers emergency repair on error.

- [ ] **Step 1: Write the failing test for Task 2 in `tests/test_upgrade_pipeline.sh`**

Append to `tests/test_upgrade_pipeline.sh`:

```bash
# --- Task 2: Staged Upgrade & Emergency Repair Tests ---
echo "=================================================="
echo "Running Staged Upgrade & Emergency Repair Tests"
echo "=================================================="

# 1. Test Mocked Full Pipeline Execution
set +e
APPLY_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_MOCK_APT=1 OSM_APT_DIR="${SANDBOX_DIR}" OSM_BACKUP_DIR="${SANDBOX_BACKUP}" "${UPGRADE_SCRIPT}" --apply --non-interactive 2>&1)"
APPLY_RC=$?
set -e

assert_exit_code "Mocked full upgrade pipeline exits 0" 0 "${APPLY_RC}"
assert_contains "Executes Phase 0 Preflight" "${APPLY_OUT}" "Phase 0: Pre-Flight Verification Gate"
assert_contains "Executes Phase 1 Backup" "${APPLY_OUT}" "Phase 1: State Backup"
assert_contains "Executes Phase 2 Transition" "${APPLY_OUT}" "Phase 2: APT deb822 Repository Matrix Transition"
assert_contains "Point of No Return acknowledged" "${APPLY_OUT}" "POINT OF NO RETURN"
assert_contains "Executes Phase 3 Minimal Upgrade" "${APPLY_OUT}" "Phase 3: Minimal Safe Upgrade"
assert_contains "Executes intermediate cache purge" "${APPLY_OUT}" "apt-get clean"
assert_contains "Queues SOF audio firmware" "${APPLY_OUT}" "firmware-sof-signed"
assert_contains "Executes Phase 4 Full Upgrade" "${APPLY_OUT}" "Phase 4: Full Distribution Upgrade"

# 2. Test Emergency DPKG Repair Trigger on APT Failure
SANDBOX_FAIL_DIR="$(mktemp -d /tmp/osm_sandbox_fail_XXXXXX)"
SANDBOX_FAIL_BACKUP="$(mktemp -d /tmp/osm_sandbox_fail_bak_XXXXXX)"
trap 'rm -rf "${SANDBOX_DIR}" "${SANDBOX_BACKUP}" "${SANDBOX_FAIL_DIR}" "${SANDBOX_FAIL_BACKUP}"' EXIT

set +e
FAIL_APPLY_OUT="$(OSM_MOCK_ROOT=1 OSM_MOCK_TMUX=1 OSM_MOCK_APT=1 OSM_MOCK_APT_FAIL=1 OSM_APT_DIR="${SANDBOX_FAIL_DIR}" OSM_BACKUP_DIR="${SANDBOX_FAIL_BACKUP}" "${UPGRADE_SCRIPT}" --apply --non-interactive 2>&1)"
FAIL_APPLY_RC=$?
set -e

assert_exit_code "Failed upgrade exits with code 3" 3 "${FAIL_APPLY_RC}"
assert_contains "Emergency repair triggered" "${FAIL_APPLY_OUT}" "Triggering Emergency DPKG Repair Protocol"
assert_contains "Runs dpkg configure" "${FAIL_APPLY_OUT}" "dpkg --configure -a"
assert_contains "Runs apt install -f" "${FAIL_APPLY_OUT}" "apt-get install -f"
assert_contains "Outputs efivars bind in rescue guidance" "${FAIL_APPLY_OUT}" "/sys/firmware/efi/efivars"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test_upgrade_pipeline.sh`
Expected output: FAIL with "Unknown option: --apply".

- [ ] **Step 3: Implement Staged Upgrade Subroutines in `scripts/upgrade_debian_trixie.sh`**

Add implementation:

```bash
run_apt_cmd() {
    local cmd=("$@")
    if [[ "${OSM_MOCK_APT:-0}" == "1" ]]; then
        log_info "[MOCK APT] Executing: ${cmd[*]}"
        if [[ "${OSM_MOCK_APT_FAIL:-0}" == "1" && "${cmd[0]}" == "apt-get" && "${cmd[1]}" == "upgrade" ]]; then
            log_error "[MOCK APT] Simulated package upgrade failure."
            return 100
        fi
        return 0
    fi

    export DEBIAN_FRONTEND=noninteractive
    export DEBIAN_PRIORITY=critical
    export NEEDRESTART_MODE=a
    export NEEDRESTART_SUSPEND=1
    export UCF_FORCE_CONFFOLD=1

    "${cmd[@]}"
}

emergency_repair_dpkg() {
    log_error "============================================================"
    log_error "CRITICAL: Upgrade failed mid-process!"
    log_error "Triggering Emergency DPKG Repair Protocol (Zero-Downgrade Invariant)..."
    log_error "============================================================"

    log_info "1. Resolving unconfigured packages: dpkg --configure -a..."
    run_apt_cmd dpkg --configure -a || true

    log_info "2. Repairing broken dependencies: apt-get install -f -y..."
    run_apt_cmd apt-get install -f -y || true

    log_warn "If the system cannot boot or packages remain broken, follow the Emergency Recovery Protocol:"
    log_warn "  Option A (Offline Host Repair - survives dynamic linker crash):"
    log_warn "    sudo mount /dev/nvme0n1p2 /mnt && sudo mount /dev/nvme0n1p1 /mnt/boot/efi"
    log_warn "    sudo dpkg --root=/mnt --configure -a"
    log_warn "    sudo apt-get -o RootDir=/mnt update && sudo apt-get -o RootDir=/mnt install -f -y"
    log_warn "  Option B (Chroot Recovery with EFI Variables):"
    log_warn "    for i in /dev /dev/pts /proc /sys /run; do sudo mount --bind \$i /mnt\$i; done"
    log_warn "    sudo mount --bind /sys/firmware/efi/efivars /mnt/sys/firmware/efi/efivars"
    log_warn "    sudo chroot /mnt"
    log_warn "    dpkg --configure -a && apt-get install -f -y && update-initramfs -u -k all && update-grub"
}

confirm_point_of_no_return() {
    echo "============================================================"
    log_warn "               *** POINT OF NO RETURN ***"
    log_warn "Debian distribution upgrade is about to unpack Trixie packages."
    log_warn "Once package unpacking begins, downgrading to Bookworm is UNSUPPORTED."
    echo "============================================================"

    if [[ "${NON_INTERACTIVE:-0}" == "1" ]]; then
        log_info "Non-interactive flag set. Proceeding past Point of No Return."
        return 0
    fi

    read -r -p "Type 'YES' to begin package installation: " confirmation
    if [[ "${confirmation}" != "YES" ]]; then
        log_error "Upgrade cancelled by user at Point of No Return."
        return 1
    fi
    return 0
}

run_minimal_upgrade() {
    log_info "Executing Phase 3: Minimal Safe Upgrade (--without-new-pkgs)..."

    log_info "Synchronizing Debian 13 package lists..."
    if ! run_apt_cmd apt-get update; then
        log_error "Failed to synchronize Debian 13 package lists."
        return 1
    fi

    log_info "Running staged minimal upgrade with needrestart suppression and package cache streaming..."
    if ! run_apt_cmd apt-get upgrade --without-new-pkgs -y \
        -o Dpkg::Options::="--force-confdef" \
        -o Dpkg::Options::="--force-confold" \
        -o APT::Keep-Downloaded-Packages="false"; then
        log_error "Minimal safe upgrade encountered an error."
        return 1
    fi

    log_info "Intermediate package cache purge to free disk headroom before full upgrade..."
    run_apt_cmd apt-get clean || true

    log_pass "Phase 3 Minimal Safe Upgrade completed successfully."
    return 0
}

install_core_firmware() {
    log_info "Installing mandatory Intel Ice Lake firmware & sound architecture (SOF + iwlwifi + misc)..."
    if ! run_apt_cmd apt-get install --no-install-recommends -y \
        firmware-sof-signed \
        firmware-iwlwifi \
        firmware-misc-nonfree \
        alsa-ucm-conf \
        -o Dpkg::Options::="--force-confdef" \
        -o Dpkg::Options::="--force-confold" \
        -o APT::Keep-Downloaded-Packages="false"; then
        log_warn "Firmware installation returned a warning; proceeding to full distribution upgrade."
    else
        log_pass "Core hardware firmware (SOF + iwlwifi + UCM + misc) installed successfully."
    fi
    return 0
}

run_full_upgrade() {
    log_info "Executing Phase 4: Full Distribution Upgrade (full-upgrade)..."

    # Ensure audio and wifi firmware are explicitly queued
    install_core_firmware

    log_info "Running apt-get full-upgrade..."
    if ! run_apt_cmd apt-get full-upgrade -y \
        -o Dpkg::Options::="--force-confdef" \
        -o Dpkg::Options::="--force-confold" \
        -o APT::Keep-Downloaded-Packages="false"; then
        log_error "Full distribution upgrade encountered an error."
        return 1
    fi

    log_info "Cleaning obsolete orphaned packages and downloaded caches..."
    run_apt_cmd apt-get autoremove --purge -y || true
    run_apt_cmd apt-get clean || true

    # Re-normalize NetworkManager keyfiles post-upgrade
    if [[ -d /etc/NetworkManager/system-connections && "${EUID}" -eq 0 ]]; then
        chmod 0600 /etc/NetworkManager/system-connections/* 2>/dev/null || true
        chown root:root /etc/NetworkManager/system-connections/* 2>/dev/null || true
    fi

    log_pass "Phase 4 Full Distribution Upgrade completed successfully."
    return 0
}

run_pipeline() {
    log_info "Starting Automated Debian 13 (Trixie) Upgrade Pipeline..."

    # Phase 0
    if ! check_preflight; then
        log_error "Aborting upgrade: Pre-Flight checks failed."
        return 2
    fi

    # Phase 1
    local timestamp current_backup_dir
    timestamp="$(date -u +"%Y%m%d_%H%M%SZ")"
    current_backup_dir="${OSM_BACKUP_DIR:-${DEFAULT_BACKUP_BASE}/apt_pre_trixie_${timestamp}}"
    export OSM_BACKUP_DIR="${current_backup_dir}"

    if ! create_backup; then
        log_error "Aborting upgrade: State backup failed."
        return 2
    fi

    # Phase 2
    if ! transition_sources; then
        log_error "Phase 2 deb822 source transition failed."
        return 2
    fi

    # Point of No Return
    if ! confirm_point_of_no_return; then
        return 1
    fi

    # Phase 3
    if ! run_minimal_upgrade; then
        emergency_repair_dpkg
        return 3
    fi

    # Phase 4
    if ! run_full_upgrade; then
        emergency_repair_dpkg
        return 3
    fi

    log_pass "============================================================"
    log_pass "Debian 13 (Trixie) Upgrade Pipeline COMPLETED SUCCESSFULLY!"
    log_pass "Please reboot the system ('sudo reboot') to initialize the new kernel."
    log_pass "============================================================"
    return 0
}
```

Update `parse_args` and `main` to handle `--apply` and `--non-interactive`.

- [ ] **Step 4: Run test to verify all Task 1 and Task 2 tests pass**

Run: `bash tests/test_upgrade_pipeline.sh`
Expected output: PASS: 22/22 passed, 0 failed.

- [ ] **Step 5: Commit Task 2 deliverables**

```bash
git add scripts/upgrade_debian_trixie.sh tests/test_upgrade_pipeline.sh
git commit -m "feat(upgrade): implement staged upgrade with cache streaming, intermediate clean, and SOF firmware"
```

---

### Task 3: Pipeline Syntax, Regression & Mock Test Suite

**Files:**
- Modify: `tests/test_upgrade_pipeline.sh`
- Test: `bash tests/test_upgrade_pipeline.sh` & `bash tests/test_upgrade_preflight.sh`.

- [ ] **Step 1: Add syntax and integrity checks in `tests/test_upgrade_pipeline.sh`**

```bash
# --- Task 3: Syntax & Integrity Checks ---
assert_exit_code "Upgrade script syntax valid" 0 $(bash -n "${UPGRADE_SCRIPT}" && echo 0 || echo 1)
assert_exit_code "Pipeline test syntax valid" 0 $(bash -n "${WORKSPACE_ROOT}/tests/test_upgrade_pipeline.sh" && echo 0 || echo 1)

echo "=================================================="
echo "Upgrade Pipeline Test Suite Complete: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0
```

- [ ] **Step 2: Run both test suites**

Run:
```bash
bash tests/test_upgrade_preflight.sh
bash tests/test_upgrade_pipeline.sh
```
Expected output: Both test suites pass 100% with exit code 0.

- [ ] **Step 3: Commit Task 3 regression tests**

```bash
git add tests/test_upgrade_pipeline.sh
git commit -m "test(upgrade): finalize Debian 13 upgrade pipeline regression suite"
```

---

## Execution Self-Review Checklist

- [x] **Spec Coverage:** Covers Phase 2 (deb822 source transition), Point of No Return gate, Phase 3 (minimal upgrade with immediate cache purge and `APT::Keep-Downloaded-Packages="false"`), and Phase 4 (full upgrade with `firmware-sof-signed`, `alsa-ucm-conf`, `firmware-misc-nonfree`, and emergency repair).
- [x] **Zero-Downgrade Invariant:** No unsupported APT source downgrades; executes `dpkg --configure -a` and `apt-get install -f` on failure.
- [x] **Emergency Rescue Protocol:** Implements offline `dpkg --root` and `efivars` chroot recovery runbooks.
- [x] **Zero-Data-Loss Adherence:** No operations touch or unmount `/dev/nvme0n1p4` (`/mnt/data`).
- [x] **deb822 Compliance:** Standardizes on `/etc/apt/sources.list.d/debian.sources` with `non-free-firmware`.
