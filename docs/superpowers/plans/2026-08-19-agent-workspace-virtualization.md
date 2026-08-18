# Agent Workspace Virtualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an unprivileged rootless container sandbox utility (`scripts/sandbox_exec.sh`) powered by Podman to encapsulate untrusted subagent commands within an isolated, read-only rootfs environment.

**Architecture:** A lightweight POSIX Bash wrapper validates target paths strictly within `/home/rizz/dev/`. It assembles hardened Podman flags (`--read-only`, `--userns=keep-id`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, `--pids-limit=256`, cgroup constraints) and propagates exit status codes. The utility operates under Tier 2 authorization boundaries, and `pre_tool_guard.sh` blocks container privilege escalation.

**Tech Stack:** Bash 5.2+, Rootless Podman, Linux user namespaces, cgroups v2 (`--memory`, `--cpus`), `jq`, `shellcheck`.

**Spec:** `docs/superpowers/specs/2026-08-19-agent-workspace-virtualization-design.md`

## Global Constraints

- **Strict Target Mount Boundary**: Sandbox target directories must reside strictly under `/home/rizz/dev/`. Target paths pointing to `/`, `/etc`, `/home/rizz/`, `/mnt/c`, or `/mnt/d` must be blocked deterministically with Exit Code 2.
- **Mandatory Hardened Sandbox Flags**: All container runs must enforce `--read-only` rootfs, `--userns=keep-id`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, and `--pids-limit=256`.
- **Pre-Authorized Tier 2 Script**: `scripts/sandbox_exec.sh` must be registered in the Tier 2 fast-path whitelist in `scripts/hooks/pre_tool_guard.sh` and `.claude/rules/safety-tiers.md`.
- **Privilege Escalation Prevention**: Raw invocations of `podman run --privileged`, `--pid=host`, `--net=host`, or `--cap-add=ALL` must remain blocked with Exit Code 2 in `pre_tool_guard.sh`.
- **Graceful Fallback When Podman Is Absent**: If `podman` is not installed or unconfigured, the script must emit an actionable diagnostic error and exit cleanly with code 1.

---

### Task 1: Create Automated Unit Test Suite for Workspace Virtualization

**Files:**
- Create: `tests/test_sandbox.sh`

**Interfaces:**
- Consumes: `scripts/sandbox_exec.sh` (`--dry-run`, `--image`, `--network`, `--mem`, `--cpus`, `--read-only`, `--target-dir`, `--`)
- Produces: Executable unit test suite verifying argument parsing, security flag assembly, workspace boundary validation, capability dropping, and exit code propagation.

- [ ] **Step 1: Write the failing unit test suite**

```bash
cat <<'EOF' > tests/test_sandbox.sh
#!/usr/bin/env bash
# tests/test_sandbox.sh - Unit tests for Agent Workspace Virtualization
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SANDBOX_SCRIPT="${WORKSPACE_ROOT}/scripts/sandbox_exec.sh"

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
echo "Running Agent Workspace Virtualization Unit Tests"
echo "=================================================="

# 1. Script existence and executable permission
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -x "${SANDBOX_SCRIPT}" ]; then
    echo "  [PASS] sandbox_exec.sh exists and is executable"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] sandbox_exec.sh missing or not executable at ${SANDBOX_SCRIPT}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 2. Test --help flag
set +e
HELP_OUT="$("${SANDBOX_SCRIPT}" --help 2>&1)"
assert_exit_code "--help flag exit code" 0 $?
assert_contains "--help output content" "${HELP_OUT}" "Usage:"
set -e

# 3. Test --dry-run standard container assembly
DRY_RUN_OUT="$("${SANDBOX_SCRIPT}" --dry-run --target-dir "${WORKSPACE_ROOT}" -- echo "hello")"
assert_contains "dry-run contains podman run" "${DRY_RUN_OUT}" "podman run"
assert_contains "dry-run contains --read-only" "${DRY_RUN_OUT}" "--read-only"
assert_contains "dry-run contains --userns=keep-id" "${DRY_RUN_OUT}" "--userns=keep-id"
assert_contains "dry-run contains --cap-drop=ALL" "${DRY_RUN_OUT}" "--cap-drop=ALL"
assert_contains "dry-run contains --security-opt=no-new-privileges" "${DRY_RUN_OUT}" "--security-opt=no-new-privileges"
assert_contains "dry-run contains --pids-limit=256" "${DRY_RUN_OUT}" "--pids-limit=256"
assert_contains "dry-run contains workspace mount" "${DRY_RUN_OUT}" "-v ${WORKSPACE_ROOT}:/workspace:rw,z"
assert_contains "dry-run contains target command" "${DRY_RUN_OUT}" "echo hello"

# 4. Test resource constraints and network flags
CUSTOM_DRY="$("${SANDBOX_SCRIPT}" --dry-run --target-dir "${WORKSPACE_ROOT}" --mem 512m --cpus 1 --network slirp4netns --read-only -- ls -la)"
assert_contains "custom memory limit" "${CUSTOM_DRY}" "--memory=512m"
assert_contains "custom cpus limit" "${CUSTOM_DRY}" "--cpus=1"
assert_contains "custom network mode" "${CUSTOM_DRY}" "--network=slirp4netns"
assert_contains "read-only mount mode" "${CUSTOM_DRY}" ":ro,z"

# 5. Test workspace boundary violation (target directory outside /home/rizz/dev/)
set +e
BOUNDARY_OUT="$("${SANDBOX_SCRIPT}" --dry-run --target-dir "/etc" -- echo "fail" 2>&1)"
BOUNDARY_EXIT=$?
assert_exit_code "Boundary violation blocked with Exit 2" 2 ${BOUNDARY_EXIT}
assert_contains "Boundary violation error message" "${BOUNDARY_OUT}" "must reside strictly under /home/rizz/dev/"

WINDOWS_MOUNT_OUT="$("${SANDBOX_SCRIPT}" --dry-run --target-dir "/mnt/c/Windows" -- echo "fail" 2>&1)"
WINDOWS_MOUNT_EXIT=$?
assert_exit_code "Windows mount target blocked with Exit 2" 2 ${WINDOWS_MOUNT_EXIT}
set -e

echo "=================================================="
echo "Workspace Virtualization Unit Tests Complete: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0
EOF
chmod +x tests/test_sandbox.sh
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./tests/test_sandbox.sh`
Expected: FAIL because `scripts/sandbox_exec.sh` does not exist or lacks parameters.

- [ ] **Step 3: Create stub script to confirm test execution failure signature**

```bash
cat <<'EOF' > scripts/sandbox_exec.sh
#!/usr/bin/env bash
# scripts/sandbox_exec.sh - Stub for sandbox execution wrapper
echo "sandbox_exec stub" >&2
exit 1
EOF
chmod +x scripts/sandbox_exec.sh
```

- [ ] **Step 4: Run unit test runner to verify expected failure**

Run: `./tests/test_sandbox.sh`
Expected: FAIL with failed assertions on `--help`, `--dry-run`, and boundary validation.

- [ ] **Step 5: Commit test suite**

```bash
git add tests/test_sandbox.sh scripts/sandbox_exec.sh
git commit -m "test(sandbox): add unit test suite for agent workspace virtualization"
```

---

### Task 2: Implement Agent Workspace Virtualization Wrapper Script

**Files:**
- Modify: `scripts/sandbox_exec.sh`
- Test: `tests/test_sandbox.sh`

**Interfaces:**
- Consumes: CLI parameters (`--image`, `--network`, `--mem`, `--cpus`, `--read-only`, `--dry-run`, `--target-dir`, `-- <command>`), `podman`.
- Produces: Hardened Podman container execution with strict cgroups, dropped Linux capabilities, unprivileged user namespace, and workspace volume isolation.

- [ ] **Step 1: Implement full `scripts/sandbox_exec.sh` script**

```bash
cat <<'EOF' > scripts/sandbox_exec.sh
#!/usr/bin/env bash
# scripts/sandbox_exec.sh - Rootless container sandbox execution wrapper
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Default Configuration
IMAGE="docker.io/library/debian:13-slim"
NETWORK_MODE="none"
MEMORY_LIMIT="2g"
CPU_LIMIT="2"
READ_ONLY=false
DRY_RUN=false
TARGET_DIR="${PWD}"

show_help() {
    cat <<HELP
Usage: $(basename "$0") [OPTIONS] [-- <command...>]

Execute untrusted subagent tasks in a hardened rootless container sandbox.

Options:
  --image <image>        Base container image (default: "docker.io/library/debian:13-slim")
  --network <mode>       Network mode: none | slirp4netns | host (default: "none")
  --mem <limit>          Memory limit with unit (default: "2g")
  --cpus <count>         Allocated virtual CPU cores (default: "2")
  --read-only            Mount workspace directory as read-only volume
  --target-dir <path>    Workspace path to mount (default: current working directory)
  --dry-run              Print constructed podman command without executing
  -h, --help             Show this help message and exit

Security Invariants:
  - Target directory must reside strictly under /home/rizz/dev/
  - Container root filesystem is mounted --read-only
  - Linux capabilities dropped via --cap-drop=ALL
  - Enforces --security-opt=no-new-privileges and --pids-limit=256
  - User namespace UID mapping preserved via --userns=keep-id
HELP
}

COMMAND_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --image)
            IMAGE="$2"
            shift 2
            ;;
        --network)
            NETWORK_MODE="$2"
            shift 2
            ;;
        --mem)
            MEMORY_LIMIT="$2"
            shift 2
            ;;
        --cpus)
            CPU_LIMIT="$2"
            shift 2
            ;;
        --read-only)
            READ_ONLY=true
            shift
            ;;
        --target-dir)
            TARGET_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        --)
            shift
            COMMAND_ARGS=("$@")
            break
            ;;
        *)
            if [ -z "${COMMAND_ARGS[*]:-}" ]; then
                COMMAND_ARGS=("$@")
                break
            fi
            ;;
    esac
done

# Validate Target Workspace Boundary: strictly under /home/rizz/dev/
CANONICAL_TARGET="$(realpath -m "${TARGET_DIR}" 2>/dev/null || echo "${TARGET_DIR}")"
if [[ ! "${CANONICAL_TARGET}" =~ ^/home/rizz/dev(/|$) ]]; then
    echo "[SECURITY ERROR] Sandbox target directory must reside strictly under /home/rizz/dev/: ${TARGET_DIR}" >&2
    exit 2
fi

if [ ${#COMMAND_ARGS[@]} -eq 0 ] && [ "${DRY_RUN}" = false ]; then
    echo "Error: No command specified to execute." >&2
    show_help >&2
    exit 1
fi

# Determine Mount Permissions
MOUNT_MODE="rw"
if [ "${READ_ONLY}" = true ]; then
    MOUNT_MODE="ro"
fi

# Assemble Podman Command
PODMAN_CMD=(
    podman run
    --rm
    -i
    --read-only
    --userns=keep-id
    --network="${NETWORK_MODE}"
    --memory="${MEMORY_LIMIT}"
    --cpus="${CPU_LIMIT}"
    --pids-limit=256
    --cap-drop=ALL
    --security-opt=no-new-privileges
    -v "${CANONICAL_TARGET}:/workspace:${MOUNT_MODE},z"
    -w /workspace
    "${IMAGE}"
    "${COMMAND_ARGS[@]}"
)

if [ "${DRY_RUN}" = true ]; then
    echo "${PODMAN_CMD[*]}"
    exit 0
fi

# Verify Podman Availability
if ! command -v podman >/dev/null 2>&1; then
    echo "[ERROR] Podman is not installed. Install via your package manager (e.g., sudo apt install -y podman)" >&2
    exit 1
fi

# Execute Command in Sandbox Container
"${PODMAN_CMD[@]}"
EOF
chmod +x scripts/sandbox_exec.sh
```

- [ ] **Step 2: Run unit tests to verify pass**

Run: `./tests/test_sandbox.sh`
Expected: PASS (all assertions pass with 0 failures).

- [ ] **Step 3: Verify shellcheck compliance**

Run: `shellcheck -s bash scripts/sandbox_exec.sh`
Expected: Clean exit with 0 errors/warnings.

- [ ] **Step 4: Commit sandbox wrapper implementation**

```bash
git add scripts/sandbox_exec.sh
git commit -m "feat(sandbox): implement rootless container workspace virtualization wrapper"
```

---

### Task 3: Verify PreToolGuard Whitelist and Invariant Interception

**Files:**
- Modify: `scripts/hooks/pre_tool_guard.sh`
- Test: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `scripts/hooks/pre_tool_guard.sh`
- Produces: Guaranteed Tier 2 authorization for `scripts/sandbox_exec.sh` while blocking raw `podman run --privileged` escalations.

- [ ] **Step 1: Verify `scripts/hooks/pre_tool_guard.sh` whitelists `sandbox_exec`**

Inspect lines 103-111 of `scripts/hooks/pre_tool_guard.sh`:
Confirm `sandbox_exec` is included in `TIER2_SCRIPTS`:
`TIER2_SCRIPTS="sys_diag|clean_system|update_runtimes|wsl_snapshot|dotfiles_sync|tmux_agents|harness_check|perf_tune|manage_timers|compact_host_disk|notify_host|hook_benchmark|bus_send|post_bootstrap|sandbox_exec"`

- [ ] **Step 2: Verify `pre_tool_guard.sh` blocks container privilege escalation**

Confirm `pre_tool_guard.sh` contains:
```bash
if echo "${CMD}" | grep -qE '\bpodman\s+run\b.*(--privileged|--pid=host|--net=host|--cap-add=ALL|-v\s+/(dev|proc|sys|root|etc))\b'; then
    echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Container privilege escalation is strictly forbidden: ${CMD}" >&2
    exit 2
fi
```

- [ ] **Step 3: Test Tier 2 sandbox execution via `pre_tool_guard.sh`**

```bash
PAYLOAD_TIER2_SANDBOX='{"tool_name":"Bash","tool_input":{"command":"./scripts/sandbox_exec.sh --dry-run -- ls"}}'
echo "${PAYLOAD_TIER2_SANDBOX}" | ./scripts/hooks/pre_tool_guard.sh
```
Expected: Exit code 0.

- [ ] **Step 4: Test Tier 3 block on `podman run --privileged` via `pre_tool_guard.sh`**

```bash
PAYLOAD_TIER3_PODMAN='{"tool_name":"Bash","tool_input":{"command":"podman run --privileged ubuntu bash"}}'
echo "${PAYLOAD_TIER3_PODMAN}" | ./scripts/hooks/pre_tool_guard.sh
```
Expected: Exit code 2.

---

### Task 4: Master Harness Integration and Verification

**Files:**
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `tests/test_sandbox.sh`, `scripts/sandbox_exec.sh`
- Produces: Automated assertions in master test runner verifying script syntax, `--dry-run` parameter assembly, workspace boundary rejection, and unit test suite completion.

- [ ] **Step 1: Check existing assertions in `tests/test_harness.sh`**

Run: `grep -q "test_sandbox.sh" tests/test_harness.sh`
Expected: FAIL (assertion not yet present).

- [ ] **Step 2: Add sandbox virtualization test assertions to `tests/test_harness.sh`**

Append the sandbox test block to `tests/test_harness.sh`:

```bash
cat <<'EOF' >> tests/test_harness.sh

echo "--- Testing Agent Workspace Virtualization Suite ---"
set +e
"${WORKSPACE_ROOT}/scripts/sandbox_exec.sh" --help > /dev/null 2>&1
assert_exit_code "sandbox_exec.sh --help execution" 0 $?

DRY_RUN_SANDBOX="$("${WORKSPACE_ROOT}/scripts/sandbox_exec.sh" --dry-run --target-dir "${WORKSPACE_ROOT}" -- echo "test")"
echo "${DRY_RUN_SANDBOX}" | grep -q -- "--read-only"
assert_exit_code "sandbox_exec.sh --dry-run contains --read-only" 0 $?

"${WORKSPACE_ROOT}/tests/test_sandbox.sh" > /dev/null 2>&1
assert_exit_code "test_sandbox.sh complete suite" 0 $?
set -e
EOF
```

- [ ] **Step 3: Run the full harness test suite**

Run: `./tests/test_harness.sh`
Expected: All 41+ assertions pass with 0 failures.

- [ ] **Step 4: Run harness self-check**

Run: `./scripts/harness_check.sh`
Expected: Pass with 0 errors.

- [ ] **Step 5: Commit `tests/test_harness.sh`**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate sandbox virtualization assertions into master harness"
```

---

## Plan Self-Review Checklist

- **Spec Coverage:** 
  - Rootless Podman wrapper (`scripts/sandbox_exec.sh`) is implemented in Task 2.
  - Workspace boundary restriction strictly under `/home/rizz/dev/` is tested in Task 1 and implemented in Task 2.
  - Mandatory security flags (`--read-only`, `--userns=keep-id`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, `--pids-limit=256`) are tested in Task 1 and implemented in Task 2.
  - Tier 2 whitelist registration and Tier 3 privilege escalation blocking are verified in Task 3.
  - Master test harness assertions are verified in Task 4.
- **Placeholder Scan:** Zero instances of "TBD", "TODO", "implement later", or ambiguous ellipses.
- **Type Consistency:** Parameters (`--image`, `--network`, `--mem`, `--cpus`, `--read-only`, `--target-dir`, `--dry-run`, `--`) are uniform across all tasks.
