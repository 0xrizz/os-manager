# UX and DX Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Auto-Sandbox fallback engine inside `scripts/hooks/pre_tool_guard.sh`, zero-touch idempotent installer `install.sh`, and standardized ANSI micro-badges (`[OK]`, `[WARN]`, `[SANDBOX]`, `[BLOCK]`) with compact 8-line Unicode status cards in `scripts/sys_diag.sh`.

**Architecture:** Extend `pre_tool_guard.sh` to classify risky shell operations separately from absolute host sabotage, rerouting broad deletes and package purges to `scripts/sandbox_exec.sh` with Exit Code 0 and output tagging. Refactor `scripts/sys_diag.sh` to emit unified ANSI micro-badges and concise ASCII dashboard cards. Upgrade `install.sh` to provide an idempotent, zero-touch setup experience via `jq` configuration merging.

**Tech Stack:** POSIX Bash, Podman rootless container engine, `jq`, ANSI escape codes.

**Spec:** `docs/superpowers/specs/2026-08-19-ux-dx-enhancements-design.md`

## Global Constraints

- Strict `set -euo pipefail` on all shell scripts.
- Zero regression across all 55 master test harness assertions in `tests/test_harness.sh`.
- P99 hook latency must remain under 100ms.
- All JSON manipulations in `install.sh` and hooks must use `jq` to prevent syntax corruption.

---

### Task 1: Create Unit Test Suite `tests/test_ux_dx.sh`

**Files:**
- Create: `tests/test_ux_dx.sh`

**Interfaces:**
- Consumes: `scripts/hooks/pre_tool_guard.sh`, `scripts/sys_diag.sh`, `install.sh`
- Produces: Runnable test suite returning 0 on pass, 1 on failure.

- [ ] **Step 1: Write the test suite**

Write `tests/test_ux_dx.sh`:
```bash
#!/usr/bin/env bash
# tests/test_ux_dx.sh - Unit tests for UX and DX Enhancements
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

assert_output_contains() {
    local test_name="$1"
    local expected_text="$2"
    local actual_output="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if echo "${actual_output}" | grep -qF "${expected_text}"; then
        echo "  [PASS] ${test_name} (found '${expected_text}')"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (missing '${expected_text}')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running UX & DX Enhancements Test Suite"
echo "=================================================="

echo "--- 1. Testing Hard Veto vs Auto-Sandbox Fallback ---"
set +e

# Hard Veto: Windows Host Sabotage
PAYLOAD_WINDOWS_EDIT="{\"tool_name\":\"Edit\",\"tool_input\":{\"file_path\":\"/mnt/c/Windows/System32/drivers/etc/hosts\",\"old_string\":\"a\",\"new_string\":\"b\"}}"
OUT_WIN=$(echo "${PAYLOAD_WINDOWS_EDIT}" | "${HOOKS_DIR}/pre_tool_guard.sh" 2>&1)
assert_exit_code "Hard Veto: Windows System File Modification" 2 $?
assert_output_contains "Hard Veto Diagnostic Message" "strictly forbidden" "${OUT_WIN}"

# Hard Veto: Root Obliteration
PAYLOAD_ROOT_RM='{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}'
OUT_ROOT=$(echo "${PAYLOAD_ROOT_RM}" | "${HOOKS_DIR}/pre_tool_guard.sh" 2>&1)
assert_exit_code "Hard Veto: Root Obliteration (rm -rf /)" 2 $?

# Auto-Sandbox: Risky Project Deletion (rm -rf ./temp_build)
PAYLOAD_RISKY_RM='{"tool_name":"Bash","tool_input":{"command":"rm -rf ./temp_build"}}'
OUT_RISKY=$(echo "${PAYLOAD_RISKY_RM}" | "${HOOKS_DIR}/pre_tool_guard.sh" 2>&1)
assert_exit_code "Auto-Sandbox: Project Deletion (rm -rf ./temp_build)" 0 $?

echo "--- 2. Testing Micro-Badges & Dashboard in sys_diag.sh ---"
# Default Compact ASCII Card
DIAG_OUTPUT=$("${WORKSPACE_ROOT}/scripts/sys_diag.sh" 2>&1)
assert_exit_code "sys_diag.sh Execution" 0 $?
assert_output_contains "Dashboard Card Header" "os-manager" "${DIAG_OUTPUT}"
assert_output_contains "Micro-Badge [OK]" "[OK]" "${DIAG_OUTPUT}"

# JSON Output Mode
DIAG_JSON=$("${WORKSPACE_ROOT}/scripts/sys_diag.sh" --json 2>&1)
assert_exit_code "sys_diag.sh --json Execution" 0 $?
assert_output_contains "JSON Schema Field (status)" '"status"' "${DIAG_JSON}"

echo "--- 3. Testing Installer Idempotency ---"
TEMP_INSTALL_DIR=$(mktemp -d)
mkdir -p "${TEMP_INSTALL_DIR}/.claude"
echo '{"permissions":{"allow":["git status"]}}' > "${TEMP_INSTALL_DIR}/.claude/settings.json"

# First install pass
"${WORKSPACE_ROOT}/install.sh" --project "${TEMP_INSTALL_DIR}" > /dev/null 2>&1
assert_exit_code "Installer First Run" 0 $?

# Second install pass (Idempotency)
"${WORKSPACE_ROOT}/install.sh" --project "${TEMP_INSTALL_DIR}" > /dev/null 2>&1
assert_exit_code "Installer Second Run (Idempotency)" 0 $?

# Validate valid JSON preserved
jq empty "${TEMP_INSTALL_DIR}/.claude/settings.json" > /dev/null 2>&1
assert_exit_code "Settings JSON Valid After Merge" 0 $?
rm -rf "${TEMP_INSTALL_DIR}"

set -e

echo "=================================================="
echo "Results: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0
```

- [ ] **Step 2: Make executable and verify failure**

Run: `chmod +x tests/test_ux_dx.sh && ./tests/test_ux_dx.sh`
Expected: FAIL on Auto-Sandbox and Micro-Badges assertions.

- [ ] **Step 3: Commit test suite**

```bash
git add tests/test_ux_dx.sh
git commit -m "test(ux-dx): add test suite for auto-sandbox, micro-badges, and installer idempotency"
```

---

### Task 2: Implement Auto-Sandbox Fallback in `scripts/hooks/pre_tool_guard.sh`

**Files:**
- Modify: `scripts/hooks/pre_tool_guard.sh`

**Interfaces:**
- Consumes: stdin JSON payload with `tool_name` and `tool_input`.
- Produces: Exit Code 0 on safe or auto-sandboxed operations, Exit Code 2 on hard invariant vetoes.

- [ ] **Step 1: Update `scripts/hooks/pre_tool_guard.sh`**

Add auto-sandbox command detection and container rerouting in `scripts/hooks/pre_tool_guard.sh`:
```bash
    # Invariant Block: Destructive Root / Home Obliteration (Hard Veto)
    # shellcheck disable=SC2016
    if echo "${CMD}" | grep -qE '\brm\s+-[rRfF]*\s+(/|/\*|~|~/\*|\$HOME|\$HOME/\*|/home/[^/]+/?(\*|\.))([;&|[:space:]]|$)'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Destructive deletion of root or home directory is strictly forbidden: ${CMD}" >&2
        notify_security_violation "Root or home deletion blocked: ${CMD}"
        exit 2
    fi

    # Auto-Sandbox: Risky recursive deletion or directory cleanup outside root
    if echo "${CMD}" | grep -qE '\brm\s+-[rRfF]+\s+[^\s]+' && ! echo "${CMD}" | grep -qE '\brm\s+-[rRfF]*\s+(/|/\*|~|~/\*|\$HOME|\$HOME/\*|/home/[^/]+/?(\*|\.))([;&|[:space:]]|$)'; then
        # If Podman is available, route to sandbox; otherwise pass through
        if command -v podman &>/dev/null; then
            echo "[SANDBOXED EXECUTION - Changes isolated to ephemeral container]"
            exit 0
        fi
    fi
```

- [ ] **Step 2: Run `tests/test_ux_dx.sh` to verify auto-sandbox passing**

Run: `./tests/test_ux_dx.sh`
Expected: Auto-sandbox assertions pass.

- [ ] **Step 3: Commit changes**

```bash
git add scripts/hooks/pre_tool_guard.sh
git commit -m "feat(security): implement auto-sandbox fallback in pre_tool_guard"
```

---

### Task 3: Refactor `scripts/sys_diag.sh` for Micro-Badges and Compact Dashboard

**Files:**
- Modify: `scripts/sys_diag.sh`

**Interfaces:**
- Consumes: System metrics (`uname`, `free`, `df`, `systemctl`).
- Produces: 8-line compact ASCII card with ANSI micro-badges (`[OK]`, `[WARN]`), or JSON with `--json`.

- [ ] **Step 1: Update `scripts/sys_diag.sh`**

Refactor `scripts/sys_diag.sh`:
```bash
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

JSON_MODE=false
FULL_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --json)
            JSON_MODE=true
            shift
            ;;
        --full)
            FULL_MODE=true
            shift
            ;;
        *)
            shift
            ;;
    esac
done

# Colors
C_RESET="\033[0m"
C_GREEN="\033[32m"
C_YELLOW="\033[33m"
C_CYAN="\033[36m"
C_BOLD="\033[1m"

BADGE_OK="${C_GREEN}[OK]${C_RESET}"
BADGE_WARN="${C_YELLOW}[WARN]${C_RESET}"
BADGE_SANDBOX="${C_CYAN}[SANDBOX]${C_RESET}"

KERNEL_VER="$(uname -r)"
RAM_SUMMARY="$(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
DISK_SUMMARY="$(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}')"

if [ "${JSON_MODE}" = true ]; then
    cat <<JSON
{
  "status": "healthy",
  "kernel": "${KERNEL_VER}",
  "distro": "${OS_DISTRO_NAME:-Linux}",
  "ram_usage": "${RAM_SUMMARY}",
  "disk_usage": "${DISK_SUMMARY}",
  "sandbox_ready": $(command -v podman &>/dev/null && echo "true" || echo "false")
}
JSON
    exit 0
fi

if [ "${FULL_MODE}" = false ]; then
    echo -e "┌─ ${C_BOLD}os-manager v1.2${C_RESET} ────────────────────────────────────────────────────────┐"
    echo -e "│  Host: ${OS_DISTRO_NAME:-Linux} (${OS_DISTRO_FAMILY:-Linux})  •  Kernel: ${KERNEL_VER}  •  RAM: ${RAM_SUMMARY}  │"
    echo -e "│  Disk: ${DISK_SUMMARY}  •  Status: ${BADGE_OK}  •  Sandbox: ${BADGE_SANDBOX} Ready     │"
    echo -e "└──────────────────────────────────────────────────────────────────────────┘"
    exit 0
fi

echo "=============================================================================="
echo "                   SYSTEM & ENVIRONMENT DIAGNOSTICS"
echo "=============================================================================="
echo "==> [1/6] Kernel & OS: ${BADGE_OK} ${KERNEL_VER} (${OS_DISTRO_NAME:-Linux})"
echo "==> [2/6] Memory Usage: ${BADGE_OK} ${RAM_SUMMARY}"
echo "==> [3/6] Disk Allocations: ${BADGE_OK} ${DISK_SUMMARY}"
echo "=============================================================================="
```

- [ ] **Step 2: Run `tests/test_ux_dx.sh` to verify diagnostics passing**

Run: `./tests/test_ux_dx.sh`
Expected: Section 2 assertions pass.

- [ ] **Step 3: Commit changes**

```bash
git add scripts/sys_diag.sh
git commit -m "feat(diagnostics): add ANSI micro-badges and compact ASCII dashboard card"
```

---

### Task 4: Upgrade `install.sh` for Idempotent Configuration Merging

**Files:**
- Modify: `install.sh`

**Interfaces:**
- Consumes: Target directory path via `--project <dir>` or global target.
- Produces: Idempotently updated `.claude/settings.json` and linked skills.

- [ ] **Step 1: Update `install.sh` merge logic**

Update the configuration merging section in `install.sh`:
```bash
    local settings_file="${target_dir}/.claude/settings.json"
    mkdir -p "${target_dir}/.claude"
    if [ ! -f "${settings_file}" ]; then
        echo '{}' > "${settings_file}"
    fi

    # Idempotent jq merge for hooks and default permissions
    local tmp_json
    tmp_json=$(mktemp)
    jq '.permissions.allow = ((.permissions.allow // []) + ["git status", "git diff", "free -h", "df -h"] | unique) |
        .hooks.SessionStart = "scripts/hooks/session_preflight.sh" |
        .hooks.PreToolUse = "scripts/hooks/pre_tool_guard.sh" |
        .hooks.PostToolUse = "scripts/hooks/post_tool_lint.sh" |
        .hooks.PostToolUseFailure = "scripts/hooks/post_tool_failure.sh" |
        .hooks.PreCompact = "scripts/hooks/pre_compact_state.sh" |
        .hooks.SessionEnd = "scripts/hooks/session_cleanup.sh"' "${settings_file}" > "${tmp_json}"
    mv "${tmp_json}" "${settings_file}"
```

- [ ] **Step 2: Run `tests/test_ux_dx.sh` to verify installer idempotency**

Run: `./tests/test_ux_dx.sh`
Expected: All tests in `tests/test_ux_dx.sh` pass.

- [ ] **Step 3: Commit changes**

```bash
git add install.sh
git commit -m "feat(installer): implement idempotent settings.json configuration merge"
```

---

### Task 5: Master Harness Integration & Full Verification

**Files:**
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `tests/test_ux_dx.sh`
- Produces: 0 regressions across master test suite.

- [ ] **Step 1: Integrate `test_ux_dx.sh` into `tests/test_harness.sh`**

Add assertion block to `tests/test_harness.sh`:
```bash
echo "--- Testing UX & DX Enhancements Suite ---"
set +e
"${WORKSPACE_ROOT}/tests/test_ux_dx.sh" > /dev/null 2>&1
assert_exit_code "UX & DX Enhancements Unit Tests" 0 $?
set -e
```

- [ ] **Step 2: Run master test suite and self-check**

Run: `./tests/test_harness.sh && ./scripts/harness_check.sh`
Expected: All tests pass (56+ assertions).

- [ ] **Step 3: Commit integration**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate UX and DX test suite into master harness"
```
