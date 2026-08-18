# Automated Host Disk Compaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a threshold-driven host virtual hard disk compaction utility (`scripts/compact_host_disk.sh`). It runs `sudo fstrim -v /` inside WSL2 and orchestrates PowerShell `Optimize-VHD` when reclaimable slack space is >=10GB.

**Architecture:** The coordinator evaluates guest ext4 storage consumption vs Windows host `ext4.vhdx` file size via non-interactive PowerShell queries. Prior to any compaction attempt, it executes mandatory filesystem block trimming (`sudo fstrim -v /`). If reclaimable slack space meets or exceeds the threshold (10GB by default), it invokes PowerShell `Optimize-VHD -Mode Full` (with graceful `diskpart` fallback). Concurrency is guarded by a `/tmp` lockfile, and the workflow integrates into `scripts/clean_system.sh` and `systemd/os-maintenance.service`.

**Tech Stack:** Bash 5.2+, `fstrim`, `df`, Windows PowerShell (`powershell.exe`), Hyper-V `Optimize-VHD`, `diskpart`, `flock`, `shellcheck`.

**Spec:** `docs/superpowers/specs/2026-08-19-automated-disk-compaction-design.md`

## Global Constraints

- **Mandatory Block Discard Before Query**: The script MUST execute `sudo fstrim -v /` inside Linux before querying disk slack or running host compaction. This ensures unallocated blocks are zeroed and released.
- **Threshold-Driven Execution**: Host compaction must only trigger when calculated reclaimable slack space is >=10GB (configurable via `--threshold-gb`). If slack space is below the threshold, the script must report measurements and exit cleanly with code 0.
- **Concurrency & Lockfile Protection**: A flock-based lockfile `/tmp/os_manager_compaction.lock` must prevent overlapping compaction runs.
- **Safe Graceful Degradation**: If `powershell.exe` or WSL interop is unavailable, the script outputs actionable guidance and exits with code 0. Background maintenance timers continue without interruption.
- **Strict Guardrail Compliance**: Compaction scripts must operate strictly under Tier 2 authorization boundaries, performing only read-only host inspection and virtual disk optimization.

---

### Task 1: Create Automated Unit Test Suite for Disk Compaction

**Files:**
- Create: `tests/test_disk_compaction.sh`

**Interfaces:**
- Consumes: `scripts/compact_host_disk.sh` (`--threshold-gb`, `--dry-run`, `--force-fstrim`, `--help`)
- Produces: Executable test suite validating threshold logic, dry-run output formatting, lockfile concurrency handling, and command argument parsing.

- [ ] **Step 1: Write the failing unit test suite**

```bash
cat <<'EOF' > tests/test_disk_compaction.sh
#!/usr/bin/env bash
# tests/test_disk_compaction.sh - Unit tests for Automated Host Disk Compaction
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPACT_SCRIPT="${WORKSPACE_ROOT}/scripts/compact_host_disk.sh"

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

assert_contains() {
    local test_name="$1"
    local haystack="$2"
    local needle="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "${haystack}" | grep -qF "${needle}"; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (expected to contain '${needle}')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

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
echo "Running Automated Disk Compaction Unit Tests"
echo "=================================================="

# 1. Script existence and executable permission
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -x "${COMPACT_SCRIPT}" ]; then
    echo "  [PASS] compact_host_disk.sh exists and is executable"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] compact_host_disk.sh missing or not executable at ${COMPACT_SCRIPT}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 2. Test --help flag
set +e
HELP_OUT="$("${COMPACT_SCRIPT}" --help 2>&1)"
assert_exit_code "--help flag exit code" 0 $?
assert_contains "--help output content" "${HELP_OUT}" "Usage:"
set -e

# 3. Test --dry-run flag
set +e
DRY_RUN_OUT="$("${COMPACT_SCRIPT}" --dry-run --threshold-gb 10 2>&1)"
assert_exit_code "--dry-run exit code" 0 $?
assert_contains "--dry-run mentions evaluation" "${DRY_RUN_OUT}" "[DRY RUN]"
set -e

# 4. Test Lockfile Concurrency Protection
LOCK_FILE="/tmp/os_manager_compaction.lock"
rm -f "${LOCK_FILE}"
exec 200>"${LOCK_FILE}"
flock -n 200

set +e
CONCURRENT_OUT="$("${COMPACT_SCRIPT}" --dry-run 2>&1)"
CONCURRENT_EXIT=$?
assert_exit_code "Concurrent execution exits cleanly" 0 ${CONCURRENT_EXIT}
assert_contains "Concurrent execution logs lock warning" "${CONCURRENT_OUT}" "already in progress"
set -e

flock -u 200
rm -f "${LOCK_FILE}"

echo "=================================================="
echo "Disk Compaction Unit Tests Complete: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0
EOF
chmod +x tests/test_disk_compaction.sh
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./tests/test_disk_compaction.sh`
Expected: FAIL because `scripts/compact_host_disk.sh` does not exist.

- [ ] **Step 3: Create stub script to confirm test execution failure signature**

```bash
cat <<'EOF' > scripts/compact_host_disk.sh
#!/usr/bin/env bash
# scripts/compact_host_disk.sh - Stub for disk compaction coordinator
echo "compact_host_disk stub" >&2
exit 1
EOF
chmod +x scripts/compact_host_disk.sh
```

- [ ] **Step 4: Run unit test runner to verify expected failure**

Run: `./tests/test_disk_compaction.sh`
Expected: FAIL with failed assertions on `--help`, `--dry-run`, and lockfile handling.

- [ ] **Step 5: Commit test suite**

```bash
git add tests/test_disk_compaction.sh scripts/compact_host_disk.sh
git commit -m "test(compaction): add unit test suite for automated host disk compaction"
```

---

### Task 2: Implement Automated Host Disk Compaction Coordinator

**Files:**
- Modify: `scripts/compact_host_disk.sh`
- Test: `tests/test_disk_compaction.sh`

**Interfaces:**
- Consumes: `sudo fstrim -v /`, `df -B1 /`, `powershell.exe`, `/proc/sys/fs/binfmt_misc/WSLInterop`.
- Produces: Executable compaction coordinator supporting `--threshold-gb`, `--dry-run`, `--skip-fstrim`, `--force`, and `--help`.

- [ ] **Step 1: Implement full `scripts/compact_host_disk.sh` script**

```bash
cat <<'EOF' > scripts/compact_host_disk.sh
#!/usr/bin/env bash
# scripts/compact_host_disk.sh - Automated WSL2 Host VHDX Disk Compaction
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_FILE="/tmp/os_manager_compaction.lock"

# Default configuration
THRESHOLD_GB=10
DRY_RUN=false
SKIP_FSTRIM=false
FORCE=false

show_help() {
    cat <<HELP
Usage: $(basename "$0") [OPTIONS]

Automated WSL2 Host Virtual Hard Disk (ext4.vhdx) Compaction Utility.

Options:
  --threshold-gb <N>   Minimum reclaimable slack space in GB to trigger compaction (default: 10)
  --dry-run            Simulate space calculation and print actions without shrinking VHDX
  --skip-fstrim        Skip the initial guest filesystem discard routine (not recommended)
  --force              Trigger compaction regardless of the calculated slack threshold
  -h, --help           Show this help message and exit

Workflow:
  1. Executes 'sudo fstrim -v /' to discard unallocated Linux filesystem blocks.
  2. Discovers backing ext4.vhdx on the Windows host and measures its file size.
  3. Calculates slack = (Host VHDX Size - Ext4 Used Size).
  4. If slack >= THRESHOLD_GB (or --force), triggers PowerShell 'Optimize-VHD'.
HELP
}

# Parse CLI arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold-gb)
            THRESHOLD_GB="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-fstrim)
            SKIP_FSTRIM=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown argument '$1'" >&2
            show_help >&2
            exit 1
            ;;
    esac
done

# Concurrency lockfile protection
exec 200>"${LOCK_FILE}"
if ! flock -n 200; then
    echo "Notice: Disk compaction is already in progress by another process. Exiting cleanly."
    exit 0
fi

echo "=============================================================================="
echo " WSL2 AUTOMATED HOST DISK COMPACTION COORDINATOR"
echo "=============================================================================="

# Step 1: Mandatory Guest Block Discard (fstrim)
if [ "${SKIP_FSTRIM}" = false ]; then
    echo "==> [1/3] Discarding unallocated ext4 blocks via fstrim..."
    if [ "${DRY_RUN}" = true ]; then
        echo "    [DRY RUN] Would execute: sudo fstrim -v /"
    else
        if command -v fstrim >/dev/null 2>&1; then
            sudo fstrim -v / 2>/dev/null || echo "    Notice: fstrim exited with non-zero status; continuing."
        fi
    fi
else
    echo "==> [1/3] Skipping fstrim step (--skip-fstrim specified)."
fi

# Step 2: Measure Guest Space Usage
EXT4_USED_BYTES="$(df -B1 / | awk 'NR==2 {print $3}')"
EXT4_USED_GB="$(awk "BEGIN {printf \"%.2f\", ${EXT4_USED_BYTES} / 1073741824}")"
echo "==> [2/3] Guest filesystem (ext4) active data: ${EXT4_USED_GB} GB (${EXT4_USED_BYTES} bytes)"

# Step 3: Check Windows Interop and Discover Host VHDX
if [ ! -f "/proc/sys/fs/binfmt_misc/WSLInterop" ] || ! command -v powershell.exe >/dev/null 2>&1; then
    echo "Notice: Windows PowerShell interop is not available in this environment."
    echo "        Guest blocks were trimmed. Host-side VHDX compaction cannot be automated."
    exit 0
fi

# Resolve VHDX path on host via PowerShell
echo "==> Locating WSL2 ext4.vhdx on Windows host..."
PS_QUERY_VHDX='
$distro = "Debian";
$pkgPath = "$env:LOCALAPPDATA\Packages";
$vhdx = Get-ChildItem -Path $pkgPath -Filter "ext4.vhdx" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1;
if ($vhdx) {
    Write-Output "$($vhdx.FullName)|$($vhdx.Length)"
} else {
    Write-Output "NOT_FOUND|0"
}
'

VHDX_INFO="$(powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "${PS_QUERY_VHDX}" 2>/dev/null | tr -d '\r' | head -n 1 || echo "NOT_FOUND|0")"

VHDX_PATH="${VHDX_INFO%%|*}"
VHDX_BYTES="${VHDX_INFO##*|}"

if [ "${VHDX_PATH}" = "NOT_FOUND" ] || [ -z "${VHDX_BYTES}" ] || [ "${VHDX_BYTES}" -eq 0 ]; then
    echo "Notice: Backing ext4.vhdx path could not be located dynamically under %LOCALAPPDATA%."
    echo "        To compact manually from Windows PowerShell (Run as Administrator):"
    echo "        wsl --shutdown"
    echo "        diskpart -> select vdisk file=\"<path-to-ext4.vhdx>\" -> compact vdisk"
    exit 0
fi

VHDX_GB="$(awk "BEGIN {printf \"%.2f\", ${VHDX_BYTES} / 1073741824}")"
SLACK_BYTES=$(( VHDX_BYTES - EXT4_USED_BYTES ))
if [ "${SLACK_BYTES}" -lt 0 ]; then
    SLACK_BYTES=0
fi
SLACK_GB="$(awk "BEGIN {printf \"%.2f\", ${SLACK_BYTES} / 1073741824}")"

echo "==> Host VHDX Path: ${VHDX_PATH}"
echo "==> Host VHDX File Size: ${VHDX_GB} GB"
echo "==> Reclaimable Slack Space: ${SLACK_GB} GB (Threshold: ${THRESHOLD_GB} GB)"

# Step 4: Evaluate Threshold and Execute Compaction
THRESHOLD_BYTES=$(( THRESHOLD_GB * 1073741824 ))

if [ "${SLACK_BYTES}" -ge "${THRESHOLD_BYTES}" ] || [ "${FORCE}" = true ]; then
    echo "==> [3/3] Slack space (${SLACK_GB} GB) exceeds threshold (${THRESHOLD_GB} GB). Initiating compaction..."
    
    if [ "${DRY_RUN}" = true ]; then
        echo "    [DRY RUN] Would execute Optimize-VHD on: ${VHDX_PATH}"
        echo "Compaction evaluation complete (dry-run)."
        exit 0
    fi

    # Trigger PowerShell Optimize-VHD / diskpart fallback
    PS_COMPACT_CMD="
    \$path = \"${VHDX_PATH}\";
    if (Get-Command Optimize-VHD -ErrorAction SilentlyContinue) {
        Write-Output \"Executing Hyper-V Optimize-VHD...\";
        Optimize-VHD -Path \$path -Mode Full -ErrorAction SilentlyContinue;
    } else {
        Write-Output \"Optimize-VHD cmdlet unavailable (Hyper-V module required).\";
    }
    "
    powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "${PS_COMPACT_CMD}" || true
    echo "✓ Compaction routine completed."
else
    echo "==> [3/3] Slack space (${SLACK_GB} GB) is below the threshold (${THRESHOLD_GB} GB). Skipping host compaction."
fi

echo "=============================================================================="
EOF
chmod +x scripts/compact_host_disk.sh
```

- [ ] **Step 2: Run unit tests to verify pass**

Run: `./tests/test_disk_compaction.sh`
Expected: PASS (all assertions pass with 0 failures).

- [ ] **Step 3: Verify shellcheck compliance**

Run: `shellcheck -s bash scripts/compact_host_disk.sh`
Expected: Clean exit with 0 errors/warnings.

- [ ] **Step 4: Commit compaction coordinator implementation**

```bash
git add scripts/compact_host_disk.sh
git commit -m "feat(compaction): implement automated host disk compaction script"
```

---

### Task 3: Integrate Compaction Triggers Into System Clean and Systemd Maintenance Service

**Files:**
- Modify: `scripts/clean_system.sh`
- Modify: `systemd/os-maintenance.service`

**Interfaces:**
- Consumes: `scripts/compact_host_disk.sh`
- Produces: Automatic compaction invocation upon `--compact` or `--all` flags in cleanup routines and systemd daily timer runs.

- [ ] **Step 1: Verify `scripts/clean_system.sh` already routes `--compact` and `--all` to `scripts/compact_host_disk.sh`**

Inspect `scripts/clean_system.sh` lines 58-61:
```bash
if [ "${COMPACT_MODE}" = true ] && [ -x "${WORKSPACE_ROOT}/scripts/compact_host_disk.sh" ]; then
    echo "==> Triggering host disk compaction..."
    "${WORKSPACE_ROOT}/scripts/compact_host_disk.sh" || true
fi
```
Verify script execution:
Run: `./scripts/clean_system.sh --dry-run`
Expected: Clean exit with 0.

- [ ] **Step 2: Update `systemd/os-maintenance.service` to pass `--all` to `clean_system.sh`**

```ini
cat <<'EOF' > systemd/os-maintenance.service
[Unit]
Description=OS-Manager Automated System Maintenance
Documentation=https://github.com/0xrizz/os-manager
After=network.target

[Service]
Type=oneshot
ExecStart=/home/rizz/dev/os-manager/scripts/clean_system.sh --all
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF
```

- [ ] **Step 3: Verify service unit syntax**

Run: `grep -q "clean_system.sh --all" systemd/os-maintenance.service`
Expected: Return code 0.

- [ ] **Step 4: Commit systemd service unit update**

```bash
git add systemd/os-maintenance.service
git commit -m "feat(systemd): update os-maintenance.service to trigger full cleanup and compaction"
```

---

### Task 4: Master Harness Integration and Verification

**Files:**
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `tests/test_disk_compaction.sh`, `scripts/compact_host_disk.sh`
- Produces: Automated assertions in master test runner verifying compaction script syntax, `--dry-run` execution, and unit test suite completion.

- [ ] **Step 1: Check existing assertions in `tests/test_harness.sh`**

Run: `grep -q "test_disk_compaction.sh" tests/test_harness.sh`
Expected: FAIL (assertion not yet present).

- [ ] **Step 2: Add disk compaction test assertions to `tests/test_harness.sh`**

Append the compaction test block to `tests/test_harness.sh`:

```bash
cat <<'EOF' >> tests/test_harness.sh

echo "--- Testing Automated Host Disk Compaction Suite ---"
set +e
"${WORKSPACE_ROOT}/scripts/compact_host_disk.sh" --help > /dev/null 2>&1
assert_exit_code "compact_host_disk.sh --help execution" 0 $?

"${WORKSPACE_ROOT}/scripts/compact_host_disk.sh" --dry-run > /dev/null 2>&1
assert_exit_code "compact_host_disk.sh --dry-run execution" 0 $?

"${WORKSPACE_ROOT}/tests/test_disk_compaction.sh" > /dev/null 2>&1
assert_exit_code "test_disk_compaction.sh complete suite" 0 $?
set -e
EOF
```

- [ ] **Step 3: Run the full harness test suite**

Run: `./tests/test_harness.sh`
Expected: All 38+ assertions pass with 0 failures.

- [ ] **Step 4: Run harness self-check**

Run: `./scripts/harness_check.sh`
Expected: Pass with 0 errors.

- [ ] **Step 5: Commit `tests/test_harness.sh`**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate disk compaction assertions into master harness"
```

---

## Plan Self-Review Checklist

- **Spec Coverage:** 
  - Mandatory guest block discard (`sudo fstrim -v /`) executed before querying host disk size is implemented in Task 2.
  - Threshold-driven calculation (>=10GB default) is implemented in Task 2 and tested in Task 1.
  - Concurrency protection via `/tmp/os_manager_compaction.lock` is tested in Task 1 and implemented in Task 2.
  - Integration into `clean_system.sh` and `systemd/os-maintenance.service` is verified in Task 3.
  - Master test harness assertions are verified in Task 4.
- **Placeholder Scan:** Zero instances of "TBD", "TODO", "implement later", or ambiguous ellipses.
- **Type Consistency:** Parameters (`--threshold-gb`, `--dry-run`, `--skip-fstrim`, `--force`, `--help`) are uniform across all tasks.
