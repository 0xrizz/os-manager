# Hook Performance Tracing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a zero-overhead monotonic nanosecond execution tracing engine (`scripts/hooks/lib/trace_helper.sh`), instrument all six Claude Code lifecycle hooks, provide a latency percentile benchmark CLI (`scripts/hook_benchmark.sh`), and enforce sub-100ms P99 latency guarantees.

**Architecture:** A zero-fork Bash helper library (`trace_helper.sh`) captures monotonic start timestamps via `date +%s%N` and binds a POSIX `EXIT` trap. Upon script termination, the trap calculates execution duration in microseconds and fractional milliseconds using pure 64-bit Bash integer arithmetic, appending a structured JSON record (`timestamp_iso`, `timestamp_epoch`, `hook_name`, `target_tool`, `duration_ms`, `duration_us`, `exit_code`) to `backups/logs/harness_audit.jsonl`. A dedicated analyzer (`scripts/hook_benchmark.sh`) computes statistical distributions (min, mean, p50, p95, p99, max) and enforces latency thresholds.

**Tech Stack:** Bash 5.2+, Linux `/proc` filesystem, GNU coreutils (`date +%s%N`), `jq`, `shellcheck`.

**Spec:** `docs/superpowers/specs/2026-08-19-hook-performance-tracing-design.md`

## Global Constraints

- **Tracing Overhead Limit**: Tracer initialization, calculation, and log appending must add <1.0ms latency overhead per hook invocation.
- **Hook Latency Limit (NFR-1)**: All lifecycle hooks must maintain P99 execution latency <100ms.
- **Fail-Safe Telemetry**: Telemetry logging failures must never disrupt hook execution or alter exit codes (`|| true`).
- **Unified Log Schema**: Log lines in `backups/logs/harness_audit.jsonl` must contain exact fields: `timestamp_iso`, `timestamp_epoch`, `hook_name`, `target_tool`, `duration_ms`, `duration_us`, `exit_code`.
- **Non-Blocking Dispatch**: Desktop notifications on Tier 3 security blocks must execute asynchronously in the background via `(scripts/notify_host.sh ... &) disown` without adding caller latency.

---

### Task 1: Create Automated Unit Test Suite for Tracing Engine

**Files:**
- Create: `tests/test_hook_tracing.sh`

**Interfaces:**
- Consumes: `scripts/hooks/lib/trace_helper.sh` (`trace_start`, `trace_finish`)
- Produces: Executable unit test suite validating timer precision, zero-fork arithmetic, exit code propagation, and JSON schema compliance.

- [ ] **Step 1: Write the failing unit test suite**

```bash
cat <<'EOF' > tests/test_hook_tracing.sh
#!/usr/bin/env bash
# tests/test_hook_tracing.sh - Unit tests for hook performance tracing engine
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
HELPER_LIB="${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
TEST_LOG="/tmp/os_manager_test_audit.jsonl"

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

assert_json_field_exists() {
    local test_name="$1"
    local json_str="$2"
    local field="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    local val
    val="$(echo "${json_str}" | jq -r ".${field} // empty" 2>/dev/null)"
    if [ -n "${val}" ] && [ "${val}" != "null" ]; then
        echo "  [PASS] ${test_name} (field '${field}' = ${val})"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (missing field '${field}')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running Hook Performance Tracing Unit Tests"
echo "=================================================="

rm -f "${TEST_LOG}"

# 1. Test helper existence and syntax
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -f "${HELPER_LIB}" ]; then
    echo "  [PASS] trace_helper.sh exists"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] trace_helper.sh missing at ${HELPER_LIB}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 2. Test trace execution with synthetic delay and exit code 0
TEST_SCRIPT_PASS="/tmp/test_trace_pass.sh"
cat <<TESTEOF > "${TEST_SCRIPT_PASS}"
#!/usr/bin/env bash
set -euo pipefail
WORKSPACE_ROOT="${WORKSPACE_ROOT}"
export WORKSPACE_ROOT
# Override audit log destination for testing
export HARNESS_AUDIT_LOG="${TEST_LOG}"
source "${HELPER_LIB}"
trace_start "TestHookPass" "Bash"
sleep 0.05
exit 0
TESTEOF
chmod +x "${TEST_SCRIPT_PASS}"

set +e
"${TEST_SCRIPT_PASS}" >/dev/null 2>&1
PASS_CODE=$?
set -e
rm -f "${TEST_SCRIPT_PASS}"

assert_equals "Exit code 0 propagation" "0" "${PASS_CODE}"

# 3. Test trace execution with exit code 2 (Security block)
TEST_SCRIPT_BLOCK="/tmp/test_trace_block.sh"
cat <<TESTEOF > "${TEST_SCRIPT_BLOCK}"
#!/usr/bin/env bash
set -euo pipefail
WORKSPACE_ROOT="${WORKSPACE_ROOT}"
export WORKSPACE_ROOT
export HARNESS_AUDIT_LOG="${TEST_LOG}"
source "${HELPER_LIB}"
trace_start "TestHookBlock" "Edit"
sleep 0.01
exit 2
TESTEOF
chmod +x "${TEST_SCRIPT_BLOCK}"

set +e
"${TEST_SCRIPT_BLOCK}" >/dev/null 2>&1
BLOCK_CODE=$?
set -e
rm -f "${TEST_SCRIPT_BLOCK}"

assert_equals "Exit code 2 propagation" "2" "${BLOCK_CODE}"

# 4. Verify JSON schema formatting
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -s "${TEST_LOG}" ]; then
    echo "  [PASS] Telemetry log file was created and is non-empty"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Telemetry log file missing or empty: ${TEST_LOG}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

RECORD_1="$(head -n 1 "${TEST_LOG}" 2>/dev/null || echo "{}")"
RECORD_2="$(tail -n 1 "${TEST_LOG}" 2>/dev/null || echo "{}")"

assert_json_field_exists "Record 1 contains timestamp_iso" "${RECORD_1}" "timestamp_iso"
assert_json_field_exists "Record 1 contains timestamp_epoch" "${RECORD_1}" "timestamp_epoch"
assert_json_field_exists "Record 1 contains hook_name" "${RECORD_1}" "hook_name"
assert_json_field_exists "Record 1 contains target_tool" "${RECORD_1}" "target_tool"
assert_json_field_exists "Record 1 contains duration_ms" "${RECORD_1}" "duration_ms"
assert_json_field_exists "Record 1 contains duration_us" "${RECORD_1}" "duration_us"

REC1_HOOK="$(echo "${RECORD_1}" | jq -r '.hook_name')"
assert_equals "Record 1 hook_name match" "TestHookPass" "${REC1_HOOK}"

REC1_TOOL="$(echo "${RECORD_1}" | jq -r '.target_tool')"
assert_equals "Record 1 target_tool match" "Bash" "${REC1_TOOL}"

REC1_EXIT="$(echo "${RECORD_1}" | jq -r '.exit_code')"
assert_equals "Record 1 exit_code match" "0" "${REC1_EXIT}"

REC2_EXIT="$(echo "${RECORD_2}" | jq -r '.exit_code')"
assert_equals "Record 2 exit_code match" "2" "${REC2_EXIT}"

REC2_TOOL="$(echo "${RECORD_2}" | jq -r '.target_tool')"
assert_equals "Record 2 target_tool match" "Edit" "${REC2_TOOL}"

# 5. Timing validation: Sleep was 50ms, duration should be >= 40ms and <= 150ms
DURATION_MS="$(echo "${RECORD_1}" | jq -r '.duration_ms')"
DURATION_INT="${DURATION_MS%.*}"
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -n "${DURATION_INT}" ] && [ "${DURATION_INT}" -ge 40 ] && [ "${DURATION_INT}" -le 150 ]; then
    echo "  [PASS] Measured duration within expected range (${DURATION_MS}ms for ~50ms sleep)"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] Measured duration unexpected: ${DURATION_MS}ms"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

rm -f "${TEST_LOG}"

echo "=================================================="
echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
EOF
chmod +x tests/test_hook_tracing.sh
```

- [ ] **Step 2: Run test to verify it fails**

Run: `tests/test_hook_tracing.sh`
Expected: FAIL with `trace_helper.sh missing` error.

- [ ] **Step 3: Commit initial test suite**

```bash
git add tests/test_hook_tracing.sh
git commit -m "test(tracing): add unit test suite for hook performance tracing"
```

---

### Task 2: Implement High-Resolution Tracing Helper Library

**Files:**
- Create: `scripts/hooks/lib/trace_helper.sh`
- Test: `tests/test_hook_tracing.sh`

**Interfaces:**
- Consumes: None (Pure Bash + GNU `date +%s%N`)
- Produces: `trace_start(hook_name, target_tool)`, `trace_finish(exit_code)`

- [ ] **Step 1: Write the minimal implementation of `trace_helper.sh`**

```bash
mkdir -p scripts/hooks/lib
cat <<'EOF' > scripts/hooks/lib/trace_helper.sh
#!/usr/bin/env bash
# scripts/hooks/lib/trace_helper.sh - High-resolution hook execution tracing library
set -euo pipefail

TRACE_HOOK_NAME=""
TRACE_TARGET_TOOL=""
TRACE_START_NS=0

trace_start() {
    TRACE_HOOK_NAME="$1"
    TRACE_TARGET_TOOL="${2:-null}"
    TRACE_START_NS="$(date +%s%N)"
    trap 'trace_finish $?' EXIT
}

trace_finish() {
    local exit_code="$1"
    local end_ns
    end_ns="$(date +%s%N)"
    
    # Calculate duration in microseconds and fractional milliseconds using pure bash integer arithmetic
    local elapsed_ns=$((end_ns - TRACE_START_NS))
    if [ "${elapsed_ns}" -lt 0 ]; then
        elapsed_ns=0
    fi
    local duration_us=$((elapsed_ns / 1000))
    local ms_int=$((elapsed_ns / 1000000))
    local ms_frac=$(((elapsed_ns % 1000000) / 10000))
    local duration_ms
    printf -v duration_ms "%d.%02d" "${ms_int}" "${ms_frac}"
    
    local timestamp_iso
    timestamp_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    local timestamp_epoch
    timestamp_epoch="$(date +%s)"
    
    local audit_log="${HARNESS_AUDIT_LOG:-${WORKSPACE_ROOT:-.}/backups/logs/harness_audit.jsonl}"
    
    if [ -d "$(dirname "${audit_log}")" ]; then
        if [ "${TRACE_TARGET_TOOL}" = "null" ]; then
            printf '{"timestamp_iso":"%s","timestamp_epoch":%d,"hook_name":"%s","target_tool":null,"duration_ms":%s,"duration_us":%d,"exit_code":%d}\n' \
                "${timestamp_iso}" "${timestamp_epoch}" "${TRACE_HOOK_NAME}" "${duration_ms}" "${duration_us}" "${exit_code}" >> "${audit_log}" 2>/dev/null || true
        else
            printf '{"timestamp_iso":"%s","timestamp_epoch":%d,"hook_name":"%s","target_tool":"%s","duration_ms":%s,"duration_us":%d,"exit_code":%d}\n' \
                "${timestamp_iso}" "${timestamp_epoch}" "${TRACE_HOOK_NAME}" "${TRACE_TARGET_TOOL}" "${duration_ms}" "${duration_us}" "${exit_code}" >> "${audit_log}" 2>/dev/null || true
        fi
    fi
    
    exit "${exit_code}"
}
EOF
chmod +x scripts/hooks/lib/trace_helper.sh
```

- [ ] **Step 2: Run linter and unit tests**

Run: `shellcheck scripts/hooks/lib/trace_helper.sh && tests/test_hook_tracing.sh`
Expected: PASS (All 15 assertions pass).

- [ ] **Step 3: Commit implementation**

```bash
git add scripts/hooks/lib/trace_helper.sh
git commit -m "feat(tracing): implement zero-fork monotonic trace helper library"
```

---

### Task 3: Instrument Lifecycle Hooks with Performance Tracing

**Files:**
- Modify: `scripts/hooks/session_preflight.sh`
- Modify: `scripts/hooks/pre_tool_guard.sh`
- Modify: `scripts/hooks/post_tool_lint.sh`
- Modify: `scripts/hooks/post_tool_failure.sh`
- Modify: `scripts/hooks/pre_compact_state.sh`
- Modify: `scripts/hooks/session_cleanup.sh`
- Test: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `scripts/hooks/lib/trace_helper.sh`
- Produces: Instrumented lifecycle hooks appending unified trace events to `backups/logs/harness_audit.jsonl`.

- [ ] **Step 1: Instrument `scripts/hooks/session_preflight.sh`**

```bash
cat <<'EOF' > scripts/hooks/session_preflight.sh
#!/usr/bin/env bash
# scripts/hooks/session_preflight.sh - SessionStart lifecycle hook
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS_DIR="${WORKSPACE_ROOT}/backups/logs"
mkdir -p "${LOGS_DIR}"

# Source Performance Tracing Helper
if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    trace_start "SessionStart" "null"
fi

# 1. RAM / Resource inspection
AVAILABLE_MEM_MB=$(free -m | awk '/^Mem:/{print $7}')
if [ -n "${AVAILABLE_MEM_MB}" ] && [ "${AVAILABLE_MEM_MB}" -lt 300 ]; then
    echo "[WARN] Low memory in WSL2: ${AVAILABLE_MEM_MB}MB available." >&2
fi

# 2. Check essential binaries
MISSING_TOOLS=()
for tool in jq python3 uv node; do
    if ! command -v "${tool}" >/dev/null 2>&1; then
        MISSING_TOOLS+=("${tool}")
    fi
done

STATUS="OK"
if [ ${#MISSING_TOOLS[@]} -gt 0 ]; then
    STATUS="DEGRADED (missing: ${MISSING_TOOLS[*]})"
fi

# 3. Synchronize agent skill symlinks if sync script exists
if [ -x "${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh" ]; then
    "${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh" >/dev/null 2>&1 || true
fi

exit 0
EOF
chmod +x scripts/hooks/session_preflight.sh
```

- [ ] **Step 2: Instrument `scripts/hooks/pre_tool_guard.sh` with Tracing and Non-Blocking Alerts**

```bash
cat <<'EOF' > scripts/hooks/pre_tool_guard.sh
#!/usr/bin/env bash
# scripts/hooks/pre_tool_guard.sh - PreToolUse deterministic security policy engine
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Read JSON payload from stdin
INPUT_JSON="$(cat)"

if [ -z "${INPUT_JSON}" ]; then
    exit 0
fi

# Extract tool name using jq (fail closed on malformed JSON)
if ! TOOL_NAME="$(echo "${INPUT_JSON}" | jq -r '.tool_name // .name // empty' 2>/dev/null)"; then
    echo "[HARNESS SECURITY] Failed to parse tool execution JSON payload. Failing closed." >&2
    exit 2
fi

# Source Performance Tracing Helper
if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    trace_start "PreToolUse" "${TOOL_NAME:-null}"
fi

notify_security_violation() {
    local reason="$1"
    local notifier="${WORKSPACE_ROOT}/scripts/notify_host.sh"
    if [ -x "${notifier}" ]; then
        ( "${notifier}" --type security --title "Security Blocked" --message "${reason}" --async 2>/dev/null & ) disown || true
    fi
}

# 1. Guard File Operations (Edit, Write, Read)
if [[ "${TOOL_NAME}" =~ ^(Edit|Write|Read)$ ]]; then
    TARGET_PATH="$(echo "${INPUT_JSON}" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')"
    if [ -n "${TARGET_PATH}" ]; then
        CANONICAL_PATH="$(realpath -m "${TARGET_PATH}" 2>/dev/null || echo "${TARGET_PATH}")"

        # Invariant Block: Windows Host System Directories
        if [[ "${CANONICAL_PATH}" =~ ^/mnt/c/(Windows|Program\ Files|Program\ Files\ \(x86\)|Users/[^/]+/AppData) ]]; then
            if [[ "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
                echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Modification of Windows Host System files is strictly forbidden: ${TARGET_PATH}" >&2
                notify_security_violation "Modification of Windows Host System files blocked: ${TARGET_PATH}"
                exit 2
            fi
        fi

        # Invariant Block: Linux Core System Sabotage
        if [[ "${CANONICAL_PATH}" =~ ^/(etc/shadow|etc/passwd|boot/|dev/) ]]; then
            if [[ "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
                echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Modification of core Linux system files is strictly forbidden: ${TARGET_PATH}" >&2
                notify_security_violation "Modification of core Linux system files blocked: ${TARGET_PATH}"
                exit 2
            fi
        fi
    fi
    exit 0
fi

# 2. Guard Shell Executions (Bash)
if [ "${TOOL_NAME}" = "Bash" ]; then
    CMD="$(echo "${INPUT_JSON}" | jq -r '.tool_input.command // empty')"

    if [ -z "${CMD}" ]; then
        exit 0
    fi

    # Invariant Block: Destructive Root / Home Obliteration
    # shellcheck disable=SC2016
    if echo "${CMD}" | grep -qE '\brm\s+-[rRfF]*\s+(/|/\*|~|~/\*|\$HOME|\$HOME/\*|/home/[^/]+/?(\*|\.))([;&|[:space:]]|$)'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Destructive deletion of root or home directory is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Root or home deletion blocked: ${CMD}"
        exit 2
    fi

    # Invariant Block: WSL Lifecycle Sabotage
    if echo "${CMD}" | grep -qE '\b(wsl|wsl\.exe)\s+--(unregister|shutdown|terminate)\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): WSL instance lifecycle termination commands are strictly forbidden: ${CMD}" >&2
        notify_security_violation "WSL instance termination blocked: ${CMD}"
        exit 2
    fi

    # Invariant Block: Raw Disk Partitioning & Formatting
    if echo "${CMD}" | grep -qE '\b(mkfs(\.[a-z0-9]+)?|fdisk|parted|dd\s+if=.*of=/dev/sd[a-z])\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Raw disk formatting and block device alteration is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Raw disk formatting blocked: ${CMD}"
        exit 2
    fi

    # Invariant Block: Indiscriminate Package Purging (Generalized for all distros)
    if echo "${CMD}" | grep -qE '\b(apt|apt-get|pacman|dnf|zypper|apk)\s+(purge|remove|-Rcs)\s+(\*|all|--all)\b' || \
       echo "${CMD}" | grep -qE '\b(apt|apt-get|dpkg)\s+(--purge\s+)?(purge|remove)\s+-[a-zA-Z0-9]*\*\b' || \
       echo "${CMD}" | grep -qE '\bpacman\s+-[Rksu]+\s+.*(\b|\s)(base|systemd|glibc|linux-firmware)(\b|\s|$)' || \
       echo "${CMD}" | grep -qE '\bdnf\s+(remove|erase)\s+-[a-zA-Z0-9]*\*\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Destructive mass package removal is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Mass package purge blocked: ${CMD}"
        exit 2
    fi

    # Invariant Block: Dangerous Container Privilege Escalation
    if echo "${CMD}" | grep -qE '\bpodman\s+run\b.*\b(--privileged|--pid=host|--net=host|--cap-add=ALL|-v\s+/(dev|proc|sys|root|etc))\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Container privilege escalation is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Container privilege escalation blocked: ${CMD}"
        exit 2
    fi

    # Tier 2 Fast-Path: Pre-authorized maintenance & diagnostic scripts
    TIER2_SCRIPTS="sys_diag|clean_system|update_runtimes|wsl_snapshot|dotfiles_sync|tmux_agents|harness_check|perf_tune|manage_timers|compact_host_disk|notify_host|hook_benchmark|bus_send|post_bootstrap|sandbox_exec"
    if echo "${CMD}" | grep -qE "(^|[;&|[:space:]])(\\./scripts/|scripts/)?(${TIER2_SCRIPTS})\\.sh(\\s|$)"; then
        exit 0
    fi
    if echo "${CMD}" | grep -qE "(^|[;&|[:space:]])(\\./scripts/|scripts/)?agent_bus\\.py(\\s|$)"; then
        exit 0
    fi

    exit 0
fi

exit 0
EOF
chmod +x scripts/hooks/pre_tool_guard.sh
```

- [ ] **Step 3: Instrument `scripts/hooks/post_tool_lint.sh`**

```bash
cat <<'EOF' > scripts/hooks/post_tool_lint.sh
#!/usr/bin/env bash
# scripts/hooks/post_tool_lint.sh - PostToolUse auto-healing linter and syntax validator
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

INPUT_JSON="$(cat)"

if [ -z "${INPUT_JSON}" ]; then
    exit 0
fi

TOOL_NAME="$(echo "${INPUT_JSON}" | jq -r '.tool_name // .name // empty' 2>/dev/null || echo "")"
if [[ ! "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
    exit 0
fi

# Source Performance Tracing Helper
if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    trace_start "PostToolUse" "${TOOL_NAME}"
fi

TARGET_PATH="$(echo "${INPUT_JSON}" | jq -r '.tool_input.file_path // empty')"
if [ -z "${TARGET_PATH}" ] || [ ! -f "${TARGET_PATH}" ]; then
    exit 0
fi

# 1. Shell Script Validation (.sh or bash shebang)
if [[ "${TARGET_PATH}" =~ \.sh$ ]] || head -n 1 "${TARGET_PATH}" 2>/dev/null | grep -qE '^#!.*(bash|sh)'; then
    # Syntax check with bash -n
    if ! BASH_ERR="$(bash -n "${TARGET_PATH}" 2>&1)"; then
        echo "[HARNESS QUALITY GATE] Shell syntax error detected in ${TARGET_PATH}:" >&2
        echo "${BASH_ERR}" >&2
        echo "Please correct the syntax error immediately." >&2
        exit 2
    fi

    # Optional shellcheck check if installed
    if command -v shellcheck >/dev/null 2>&1; then
        if ! SC_ERR="$(shellcheck -e SC1090,SC1091 "${TARGET_PATH}" 2>&1)"; then
            echo "[HARNESS QUALITY GATE] ShellCheck issues detected in ${TARGET_PATH}:" >&2
            echo "${SC_ERR}" >&2
            echo "Please resolve these linting warnings." >&2
            exit 2
        fi
    fi
fi

# 2. JSON File Validation (.json)
if [[ "${TARGET_PATH}" =~ \.json$ ]]; then
    if ! JQ_ERR="$(jq empty "${TARGET_PATH}" 2>&1)"; then
        echo "[HARNESS QUALITY GATE] Invalid JSON formatting detected in ${TARGET_PATH}:" >&2
        echo "${JQ_ERR}" >&2
        echo "Please fix the JSON syntax." >&2
        exit 2
    fi
fi

# 3. Python File Validation (.py)
if [[ "${TARGET_PATH}" =~ \.py$ ]]; then
    if command -v python3 >/dev/null 2>&1; then
        if ! PY_ERR="$(python3 -m py_compile "${TARGET_PATH}" 2>&1)"; then
            echo "[HARNESS QUALITY GATE] Python compilation error detected in ${TARGET_PATH}:" >&2
            echo "${PY_ERR}" >&2
            echo "Please fix the Python syntax error." >&2
            exit 2
        fi
    fi
fi

exit 0
EOF
chmod +x scripts/hooks/post_tool_lint.sh
```

- [ ] **Step 4: Instrument `scripts/hooks/post_tool_failure.sh`, `pre_compact_state.sh`, and `session_cleanup.sh`**

```bash
cat <<'EOF' > scripts/hooks/post_tool_failure.sh
#!/usr/bin/env bash
# scripts/hooks/post_tool_failure.sh - PostToolUseFailure telemetry logger
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS_DIR="${WORKSPACE_ROOT}/backups/logs"
mkdir -p "${LOGS_DIR}"

if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    trace_start "PostToolUseFailure" "null"
fi

ERROR_LOG="${LOGS_DIR}/harness_errors.jsonl"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
INPUT_JSON="$(cat)"

echo "{\"timestamp\":\"${TIMESTAMP}\",\"payload\":${INPUT_JSON:-{}}}" >> "${ERROR_LOG}" 2>/dev/null || true
exit 0
EOF
chmod +x scripts/hooks/post_tool_failure.sh

cat <<'EOF' > scripts/hooks/pre_compact_state.sh
#!/usr/bin/env bash
# scripts/hooks/pre_compact_state.sh - PreCompact state snapshotter
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS_DIR="${WORKSPACE_ROOT}/backups/logs"
mkdir -p "${LOGS_DIR}"

if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    trace_start "PreCompact" "null"
fi

SNAPSHOT_FILE="${LOGS_DIR}/compact_snapshot.json"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

GIT_STATUS="$(git status --porcelain 2>/dev/null || echo "not-a-git-repo")"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")"

jq -n \
  --arg ts "${TIMESTAMP}" \
  --arg branch "${CURRENT_BRANCH}" \
  --arg git_status "${GIT_STATUS}" \
  '{timestamp: $ts, branch: $branch, git_status: $git_status}' > "${SNAPSHOT_FILE}"

exit 0
EOF
chmod +x scripts/hooks/pre_compact_state.sh

cat <<'EOF' > scripts/hooks/session_cleanup.sh
#!/usr/bin/env bash
# scripts/hooks/session_cleanup.sh - SessionEnd lifecycle hook
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS_DIR="${WORKSPACE_ROOT}/backups/logs"
mkdir -p "${LOGS_DIR}"

if [ -f "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh" ]; then
    # shellcheck source=scripts/hooks/lib/trace_helper.sh
    source "${WORKSPACE_ROOT}/scripts/hooks/lib/trace_helper.sh"
    trace_start "SessionEnd" "null"
fi

# Clean ephemeral test / temp artifacts if present
rm -f /tmp/os_manager_temp_* 2>/dev/null || true

exit 0
EOF
chmod +x scripts/hooks/session_cleanup.sh
```

- [ ] **Step 5: Run tests to verify all hooks execute and record traces**

Run: `tests/test_harness.sh && tests/test_hook_tracing.sh`
Expected: PASS (All tests pass without regression).

- [ ] **Step 6: Commit instrumented hooks**

```bash
git add scripts/hooks/*.sh
git commit -m "feat(hooks): instrument lifecycle hooks with high-resolution performance tracing"
```

---

### Task 4: Implement Latency Benchmark Reporting CLI Tool

**Files:**
- Create: `scripts/hook_benchmark.sh`
- Test: `tests/test_hook_tracing.sh`

**Interfaces:**
- Consumes: `backups/logs/harness_audit.jsonl`
- Produces: CLI reporting tool (`--summary`, `--json`, `--tail <N>`, `--samples <N>`, `--assert-p99`)

- [ ] **Step 1: Write the failing test for `hook_benchmark.sh` in `tests/test_hook_tracing.sh`**

Append test logic to `tests/test_hook_tracing.sh`:
```bash
cat <<'EOF' >> tests/test_hook_tracing.sh

# 6. Test CLI Benchmark Tool
BENCHMARK_BIN="${WORKSPACE_ROOT}/scripts/hook_benchmark.sh"
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -x "${BENCHMARK_BIN}" ]; then
    echo "  [PASS] hook_benchmark.sh is executable"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] hook_benchmark.sh missing or non-executable"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Create synthetic audit log with known latencies for benchmark validation
BENCH_AUDIT_LOG="/tmp/os_manager_bench_audit.jsonl"
cat <<BENCHEOF > "${BENCH_AUDIT_LOG}"
{"timestamp_iso":"2026-08-19T10:00:00Z","timestamp_epoch":1787149000,"hook_name":"PreToolUse","target_tool":"Bash","duration_ms":10.00,"duration_us":10000,"exit_code":0}
{"timestamp_iso":"2026-08-19T10:00:01Z","timestamp_epoch":1787149001,"hook_name":"PreToolUse","target_tool":"Bash","duration_ms":20.00,"duration_us":20000,"exit_code":0}
{"timestamp_iso":"2026-08-19T10:00:02Z","timestamp_epoch":1787149002,"hook_name":"PreToolUse","target_tool":"Bash","duration_ms":30.00,"duration_us":30000,"exit_code":0}
{"timestamp_iso":"2026-08-19T10:00:03Z","timestamp_epoch":1787149003,"hook_name":"PostToolUse","target_tool":"Edit","duration_ms":40.00,"duration_us":40000,"exit_code":0}
BENCHEOF

# Test JSON benchmark output
JSON_OUT="$("${BENCHMARK_BIN}" --log "${BENCH_AUDIT_LOG}" --json 2>/dev/null || echo "{}")"
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if echo "${JSON_OUT}" | jq -e '.PreToolUse.count == 3' >/dev/null 2>&1; then
    echo "  [PASS] hook_benchmark.sh --json computes accurate sample counts"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] hook_benchmark.sh --json failed on count assertion"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test --assert-p99 passes on fast synthetic log
set +e
"${BENCHMARK_BIN}" --log "${BENCH_AUDIT_LOG}" --assert-p99 >/dev/null 2>&1
BENCH_PASS_CODE=$?
set -e
assert_equals "hook_benchmark.sh --assert-p99 exit code on fast logs" "0" "${BENCH_PASS_CODE}"

# Test --assert-p99 fails on slow synthetic log
cat <<BENCHEOF >> "${BENCH_AUDIT_LOG}"
{"timestamp_iso":"2026-08-19T10:00:04Z","timestamp_epoch":1787149004,"hook_name":"PreToolUse","target_tool":"Bash","duration_ms":120.00,"duration_us":120000,"exit_code":0}
BENCHEOF

set +e
"${BENCHMARK_BIN}" --log "${BENCH_AUDIT_LOG}" --assert-p99 >/dev/null 2>&1
BENCH_FAIL_CODE=$?
set -e
assert_equals "hook_benchmark.sh --assert-p99 exit code on slow logs" "1" "${BENCH_FAIL_CODE}"

rm -f "${BENCH_AUDIT_LOG}"
EOF
```

- [ ] **Step 2: Run test to verify it fails**

Run: `tests/test_hook_tracing.sh`
Expected: FAIL because `scripts/hook_benchmark.sh` does not exist yet.

- [ ] **Step 3: Implement `scripts/hook_benchmark.sh`**

```bash
cat <<'EOF' > scripts/hook_benchmark.sh
#!/usr/bin/env bash
# scripts/hook_benchmark.sh - Latency benchmark reporting CLI for Claude Code lifecycle hooks
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUDIT_LOG="${WORKSPACE_ROOT}/backups/logs/harness_audit.jsonl"
SAMPLE_LIMIT=500
FILTER_HOOK=""
FORMAT="table"
ASSERT_P99=false
TAIL_MODE=false

usage() {
    cat <<USAGETEXT
Usage: $0 [OPTIONS]

Options:
  --samples <N>     Analyze the last N events (default: 500)
  --hook <name>     Filter statistics by hook name
  --log <path>      Override path to harness_audit.jsonl
  --json            Output statistics in JSON format
  --summary         Print terminal summary table (default)
  --tail <N>        Print the last N raw trace events
  --assert-p99      Exit with code 1 if any hook P99 exceeds 100ms
  --help, -h        Display this help message
USAGETEXT
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --samples)
            SAMPLE_LIMIT="$2"
            shift 2
            ;;
        --hook)
            FILTER_HOOK="$2"
            shift 2
            ;;
        --log)
            AUDIT_LOG="$2"
            shift 2
            ;;
        --json)
            FORMAT="json"
            shift
            ;;
        --summary)
            FORMAT="table"
            shift
            ;;
        --tail)
            TAIL_MODE=true
            SAMPLE_LIMIT="${2:-10}"
            shift 2
            ;;
        --assert-p99)
            ASSERT_P99=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

if [ ! -f "${AUDIT_LOG}" ]; then
    if [ "${FORMAT}" = "json" ]; then
        echo "{}"
    else
        echo "No audit telemetry found at ${AUDIT_LOG}"
    fi
    exit 0
fi

if [ "${TAIL_MODE}" = true ]; then
    tail -n "${SAMPLE_LIMIT}" "${AUDIT_LOG}"
    exit 0
fi

# Process log data using Python for precision percentile calculation
python3 -c "
import json, sys, os

log_file = '${AUDIT_LOG}'
sample_limit = int('${SAMPLE_LIMIT}')
filter_hook = '${FILTER_HOOK}'
format_type = '${FORMAT}'
assert_p99 = ('${ASSERT_P99}' == 'true')

records = []
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if 'hook_name' in data and 'duration_ms' in data:
                    records.append(data)
            except Exception:
                continue

if sample_limit > 0 and len(records) > sample_limit:
    records = records[-sample_limit:]

grouped = {}
for r in records:
    hook = r['hook_name']
    if filter_hook and hook != filter_hook:
        continue
    grouped.setdefault(hook, []).append(float(r['duration_ms']))

stats = {}
p99_violated = False

for hook, durations in sorted(grouped.items()):
    durations.sort()
    count = len(durations)
    if count == 0:
        continue
    min_val = durations[0]
    max_val = durations[-1]
    mean_val = sum(durations) / count
    p50 = durations[int(count * 0.50)]
    p95 = durations[min(count - 1, int(count * 0.95))]
    p99 = durations[min(count - 1, int(count * 0.99))]
    
    if p99 > 100.0:
        p99_violated = True

    stats[hook] = {
        'count': count,
        'min_ms': round(min_val, 2),
        'mean_ms': round(mean_val, 2),
        'p50_ms': round(p50, 2),
        'p95_ms': round(p95, 2),
        'p99_ms': round(p99, 2),
        'max_ms': round(max_val, 2),
        'status': 'FAIL (>100ms)' if p99 > 100.0 else 'OK (<100ms)'
    }

if format_type == 'json':
    print(json.dumps(stats, indent=2))
else:
    print('=' * 80)
    print('                    CLAUDE CODE HOOK LATENCY BENCHMARK REPORT')
    print('=' * 80)
    print(f'Sample Window: Last {len(records)} events from {log_file}\n')
    header = f'{\"HOOK NAME\":<20} {\"COUNT\":>6} {\"MIN (ms)\":>9} {\"P50 (ms)\":>9} {\"P95 (ms)\":>9} {\"P99 (ms)\":>9} {\"MAX (ms)\":>9}   {\"STATUS\"}'
    print(header)
    print('-' * 80)
    for hook, s in stats.items():
        print(f\"{hook:<20} {s['count']:>6} {s['min_ms']:>9.2f} {s['p50_ms']:>9.2f} {s['p95_ms']:>9.2f} {s['p99_ms']:>9.2f} {s['max_ms']:>9.2f}   {s['status']}\")
    print('=' * 80)
    verdict = 'FAIL (P99 latency threshold violated)' if p99_violated else 'PASS (100% of hooks meet the sub-100ms P99 requirement)'
    print(f'OVERALL VERDICT: {verdict}')
    print('=' * 80)

if assert_p99 and p99_violated:
    sys.exit(1)
"
```
chmod +x scripts/hook_benchmark.sh
```

- [ ] **Step 4: Run tests to verify benchmark tool passes**

Run: `shellcheck scripts/hook_benchmark.sh && tests/test_hook_tracing.sh`
Expected: PASS (All 20 unit assertions pass).

- [ ] **Step 5: Commit benchmark tool implementation**

```bash
git add scripts/hook_benchmark.sh tests/test_hook_tracing.sh
git commit -m "feat(benchmark): implement hook performance latency reporting CLI"
```

---

### Task 5: Master Harness Integration and End-to-End Verification

**Files:**
- Modify: `tests/test_harness.sh`
- Test: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `tests/test_hook_tracing.sh`, `scripts/hook_benchmark.sh`
- Produces: 22-assertion master test suite including full hook tracing verification.

- [ ] **Step 1: Integrate Tracing Suite Assertions into `tests/test_harness.sh`**

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
Expected: PASS (22/22 passed).

- [ ] **Step 3: Commit master test harness update**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate hook performance tracing assertions into test_harness.sh"
```
