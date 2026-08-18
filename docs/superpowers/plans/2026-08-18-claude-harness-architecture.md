# Claude Code Agent Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy an enterprise-grade, deterministic, and self-healing Claude Code Agent Harness for `os-manager` in Debian 13 WSL2, providing 4-tier security guardrails, auto-healing linting, custom slash commands, subagents, modular rules, and a multi-agent SSOT bridge.

**Architecture:** A Claude-First Single Source of Truth (SSOT) architecture centered in `.claude/`. Lifecycle hooks intercept tools deterministically (Exit 2 blocks/remediates), formatters & linters auto-heal edits, slash commands wrap bash automation, and zero-copy symlinks bridge skills to Universal Agent (`.agents/skills/`) and Google Antigravity (`~/.gemini/config/skills/`).

**Tech Stack:** Bash (POSIX/Bash 5+), jq, Python 3, Debian 13 (Trixie) WSL2, Claude Code Hook System (v2.x specification), Markdown.

**Spec:** `docs/superpowers/specs/2026-08-18-claude-harness-architecture.md`

## Global Constraints

- Platform: Debian GNU/Linux 13 (Trixie) WSL2 (Kernel 6.18.x) on Windows 11 host.
- Security Invariant: Strict Exit Code 2 for blocking / auto-healing remediation with error feedback on `stderr`. Exit Code 0 for allow/pass.
- Workspace Isolation: Native ext4 (`/home/rizz/`) for heavy I/O & repositories; NTFS 9P mounts (`/mnt/c/`, `/mnt/d/`) protected against host intrusion.
- SSOT Discipline: Master skills live in `.claude/skills/`; external agent paths consume relative/absolute symlinks.
- Portability: All hook paths in configuration leverage `${CLAUDE_PROJECT_DIR}` variable interpolation.
- Script Formatting: All bash scripts must have `chmod +x`, LF line endings, `set -euo pipefail`, and pass syntax validation.

---

### Task 1: Test Suite & Harness Verification Framework (`tests/test_harness.sh`)

**Files:**
- Create: `tests/test_harness.sh`

**Interfaces:**
- Consumes: None (independent test harness).
- Produces: Bash test runner CLI executing synthetic payloads against hook scripts and reporting test assertions.

- [ ] **Step 1: Write the failing test runner script**

```bash
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

# Test PreToolGuard exists
if [ ! -f "${HOOKS_DIR}/pre_tool_guard.sh" ]; then
    echo "  [FAIL] scripts/hooks/pre_tool_guard.sh does not exist"
    exit 1
fi

echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test_harness.sh`
Expected: FAIL with "scripts/hooks/pre_tool_guard.sh does not exist"

- [ ] **Step 3: Make executable and verify failure status**

Run: `chmod +x tests/test_harness.sh && ./tests/test_harness.sh || echo "Failed as expected"`
Expected: Output showing missing hook script.

- [ ] **Step 4: Commit test harness scaffold**

```bash
git add tests/test_harness.sh
git commit -m "test: add initial harness test suite runner scaffold

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Lifecycle Hook - `scripts/hooks/session_preflight.sh` & `scripts/hooks/session_cleanup.sh`

**Files:**
- Create: `scripts/hooks/session_preflight.sh`
- Create: `scripts/hooks/session_cleanup.sh`
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: Environment variables, system RAM/Swap info (`free -m`), binary paths in `$PATH`.
- Produces: Log initialization in `backups/logs/harness_audit.jsonl`, preflight validation summary, ephemeral cleanup on exit.

- [ ] **Step 1: Add Session Lifecycle test assertions to `tests/test_harness.sh`**

```bash
# Add to tests/test_harness.sh:
echo "--- Testing Session Preflight & Cleanup Hooks ---"
"${HOOKS_DIR}/session_preflight.sh" > /dev/null 2>&1
assert_exit_code "session_preflight.sh execution" 0 $?

"${HOOKS_DIR}/session_cleanup.sh" > /dev/null 2>&1
assert_exit_code "session_cleanup.sh execution" 0 $?
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test_harness.sh`
Expected: FAIL due to missing `session_preflight.sh`.

- [ ] **Step 3: Implement `scripts/hooks/session_preflight.sh`**

```bash
#!/usr/bin/env bash
# scripts/hooks/session_preflight.sh - SessionStart lifecycle hook
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS_DIR="${WORKSPACE_ROOT}/backups/logs"
mkdir -p "${LOGS_DIR}"

AUDIT_LOG="${LOGS_DIR}/harness_audit.jsonl"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

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

# 4. Log session start event
echo "{\"timestamp\":\"${TIMESTAMP}\",\"event\":\"SessionStart\",\"status\":\"${STATUS}\",\"available_mem_mb\":${AVAILABLE_MEM_MB:-0}}" >> "${AUDIT_LOG}"
exit 0
```

- [ ] **Step 4: Implement `scripts/hooks/session_cleanup.sh`**

```bash
#!/usr/bin/env bash
# scripts/hooks/session_cleanup.sh - SessionEnd lifecycle hook
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS_DIR="${WORKSPACE_ROOT}/backups/logs"
mkdir -p "${LOGS_DIR}"

AUDIT_LOG="${LOGS_DIR}/harness_audit.jsonl"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Clean ephemeral test / temp artifacts if present
rm -f /tmp/os_manager_temp_* 2>/dev/null || true

echo "{\"timestamp\":\"${TIMESTAMP}\",\"event\":\"SessionEnd\",\"status\":\"SUCCESS\"}" >> "${AUDIT_LOG}"
exit 0
```

- [ ] **Step 5: Make executable and run test suite**

Run: `chmod +x scripts/hooks/session_preflight.sh scripts/hooks/session_cleanup.sh && bash tests/test_harness.sh`
Expected: Session preflight and cleanup tests PASS.

- [ ] **Step 6: Commit session lifecycle hooks**

```bash
git add scripts/hooks/session_preflight.sh scripts/hooks/session_cleanup.sh tests/test_harness.sh
git commit -m "feat(hooks): implement SessionStart preflight and SessionEnd cleanup hooks

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Deterministic PreToolUse Guardrail - `scripts/hooks/pre_tool_guard.sh`

**Files:**
- Create: `scripts/hooks/pre_tool_guard.sh`
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: JSON input over `stdin` from Claude Code containing `tool_name` and `tool_input`.
- Produces: Exit Code `0` (allow) or Exit Code `2` (deterministic block with diagnostic feedback on `stderr`).

- [ ] **Step 1: Add 4-Tier Guardrail test cases to `tests/test_harness.sh`**

```bash
# Add to tests/test_harness.sh:
echo "--- Testing PreToolGuard 4-Tier Security Matrix ---"

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test_harness.sh`
Expected: FAIL due to missing `pre_tool_guard.sh`.

- [ ] **Step 3: Implement `scripts/hooks/pre_tool_guard.sh`**

```bash
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

# 1. Guard File Operations (Edit, Write, Read)
if [[ "${TOOL_NAME}" =~ ^(Edit|Write|Read)$ ]]; then
    TARGET_PATH="$(echo "${INPUT_JSON}" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty')"
    if [ -n "${TARGET_PATH}" ]; then
        CANONICAL_PATH="$(realpath -m "${TARGET_PATH}" 2>/dev/null || echo "${TARGET_PATH}")"
        
        # Invariant Block: Windows Host System Directories
        if [[ "${CANONICAL_PATH}" =~ ^/mnt/c/(Windows|Program\ Files|Program\ Files\ \(x86\)|Users/[^/]+/AppData) ]]; then
            if [[ "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
                echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Modification of Windows Host System files is strictly forbidden: ${TARGET_PATH}" >&2
                exit 2
            fi
        fi

        # Invariant Block: Linux Core System Sabotage
        if [[ "${CANONICAL_PATH}" =~ ^/(etc/shadow|etc/passwd|boot/|dev/) ]]; then
            if [[ "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
                echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Modification of core Linux system files is strictly forbidden: ${TARGET_PATH}" >&2
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
    if echo "${CMD}" | grep -qE '\brm\s+-[rRfF]*\s+(/|/\*|~|~/\*|\$HOME|\$HOME/\*|/home/[^/]+/?(\*|\.))(\s|$)'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Destructive deletion of root or home directory is strictly forbidden: ${CMD}" >&2
        exit 2
    fi

    # Invariant Block: WSL Lifecycle Sabotage
    if echo "${CMD}" | grep -qE '\b(wsl|wsl\.exe)\s+--(unregister|shutdown|terminate)\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): WSL instance lifecycle termination commands are strictly forbidden: ${CMD}" >&2
        exit 2
    fi

    # Invariant Block: Raw Disk Partitioning & Formatting
    if echo "${CMD}" | grep -qE '\b(mkfs(\.[a-z0-9]+)?|fdisk|parted|dd\s+if=.*of=/dev/sd[a-z])\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Raw disk formatting and block device alteration is strictly forbidden: ${CMD}" >&2
        exit 2
    fi

    # Invariant Block: Indiscriminate Package Purging
    if echo "${CMD}" | grep -qE '\b(apt|apt-get|dpkg)\s+(--purge\s+)?(purge|remove)\s+(-y\s+)?\*\b'; then
        echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Wildcard package purge is strictly forbidden: ${CMD}" >&2
        exit 2
    fi

    exit 0
fi

exit 0
```

- [ ] **Step 4: Make executable and run test suite**

Run: `chmod +x scripts/hooks/pre_tool_guard.sh && bash tests/test_harness.sh`
Expected: All PreToolGuard security tests PASS.

- [ ] **Step 5: Commit PreToolUse guardrail hook**

```bash
git add scripts/hooks/pre_tool_guard.sh tests/test_harness.sh
git commit -m "feat(hooks): implement PreToolUse 4-Tier deterministic security guardrail engine

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Auto-Healing Linting & Diagnostics Hooks - `post_tool_lint.sh`, `post_tool_failure.sh`, `pre_compact_state.sh`

**Files:**
- Create: `scripts/hooks/post_tool_lint.sh`
- Create: `scripts/hooks/post_tool_failure.sh`
- Create: `scripts/hooks/pre_compact_state.sh`
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: Tool results JSON over `stdin`, modified file contents.
- Produces: Automated lint validation (Exit 2 on syntax defect to trigger auto-healing), error telemetry logging, compact snapshots.

- [ ] **Step 1: Add Auto-Healing Linting test cases to `tests/test_harness.sh`**

```bash
# Add to tests/test_harness.sh:
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash tests/test_harness.sh`
Expected: FAIL due to missing `post_tool_lint.sh`.

- [ ] **Step 3: Implement `scripts/hooks/post_tool_lint.sh`**

```bash
#!/usr/bin/env bash
# scripts/hooks/post_tool_lint.sh - PostToolUse auto-healing linter and syntax validator
set -euo pipefail

INPUT_JSON="$(cat)"

if [ -z "${INPUT_JSON}" ]; then
    exit 0
fi

TOOL_NAME="$(echo "${INPUT_JSON}" | jq -r '.tool_name // .name // empty' 2>/dev/null || echo "")"
if [[ ! "${TOOL_NAME}" =~ ^(Edit|Write)$ ]]; then
    exit 0
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
```

- [ ] **Step 4: Implement `scripts/hooks/post_tool_failure.sh` & `scripts/hooks/pre_compact_state.sh`**

`scripts/hooks/post_tool_failure.sh`:
```bash
#!/usr/bin/env bash
# scripts/hooks/post_tool_failure.sh - PostToolUseFailure telemetry logger
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS_DIR="${WORKSPACE_ROOT}/backups/logs"
mkdir -p "${LOGS_DIR}"

ERROR_LOG="${LOGS_DIR}/harness_errors.jsonl"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
INPUT_JSON="$(cat)"

echo "{\"timestamp\":\"${TIMESTAMP}\",\"payload\":${INPUT_JSON:-{}}}" >> "${ERROR_LOG}"
exit 0
```

`scripts/hooks/pre_compact_state.sh`:
```bash
#!/usr/bin/env bash
# scripts/hooks/pre_compact_state.sh - PreCompact state snapshotter
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGS_DIR="${WORKSPACE_ROOT}/backups/logs"
mkdir -p "${LOGS_DIR}"

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
```

- [ ] **Step 5: Make executable and run test suite**

Run: `chmod +x scripts/hooks/post_tool_lint.sh scripts/hooks/post_tool_failure.sh scripts/hooks/pre_compact_state.sh && bash tests/test_harness.sh`
Expected: All linting and lifecycle hook tests PASS.

- [ ] **Step 6: Commit auto-healing linting and diagnostic hooks**

```bash
git add scripts/hooks/post_tool_lint.sh scripts/hooks/post_tool_failure.sh scripts/hooks/pre_compact_state.sh tests/test_harness.sh
git commit -m "feat(hooks): implement PostToolUse auto-healing linter, error logger, and compact state snapshotter

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Master Harness Settings Configuration (`.claude/settings.json`)

**Files:**
- Create: `.claude/settings.json`

**Interfaces:**
- Consumes: Hook scripts in `scripts/hooks/`.
- Produces: Declarative Claude Code runtime configuration for permissions, env, and hooks.

- [ ] **Step 1: Validate JSON schema structure for `.claude/settings.json`**

- [ ] **Step 2: Write `.claude/settings.json`**

```json
{
  "env": {
    "DEBUG_HARNESS": "false",
    "SHELLCHECK_OPTS": "-e SC1090,SC1091"
  },
  "permissions": {
    "defaultMode": "manual",
    "allow": [
      "Bash(./scripts/*)",
      "Bash(git status)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "Bash(free -h)",
      "Bash(df -h *)",
      "Bash(systemctl --user status *)",
      "Read(/home/rizz/dev/os-manager/**)"
    ],
    "deny": [
      "Bash(rm -rf /)",
      "Bash(rm -rf /*)",
      "Bash(rm -rf ~*)",
      "Bash(wsl --unregister*)",
      "Bash(wsl.exe --unregister*)",
      "Bash(wsl --shutdown*)",
      "Edit(/mnt/c/Windows/**)",
      "Write(/mnt/c/Windows/**)"
    ]
  },
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/scripts/hooks/session_preflight.sh",
            "timeout": 10,
            "statusMessage": "Running environment preflight checks..."
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash|Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/scripts/hooks/pre_tool_guard.sh",
            "timeout": 15,
            "statusMessage": "Validating command safety & boundaries..."
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/scripts/hooks/post_tool_lint.sh",
            "timeout": 30,
            "statusMessage": "Running static linting & syntax verification..."
          }
        ]
      }
    ],
    "PostToolUseFailure": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/scripts/hooks/post_tool_failure.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/scripts/hooks/pre_compact_state.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "${CLAUDE_PROJECT_DIR}/scripts/hooks/session_cleanup.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 3: Validate JSON syntax with `jq`**

Run: `jq empty .claude/settings.json && echo "Valid JSON"`
Expected: "Valid JSON"

- [ ] **Step 4: Commit `.claude/settings.json`**

```bash
git add .claude/settings.json
git commit -m "feat(config): configure master .claude/settings.json with permissions and lifecycle hooks

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Custom Slash Commands Palette (`.claude/commands/*.md`) & Dotfiles Script (`scripts/dotfiles_sync.sh`)

**Files:**
- Create: `scripts/dotfiles_sync.sh`
- Create: `.claude/commands/diag.md`
- Create: `.claude/commands/clean.md`
- Create: `.claude/commands/upgrade.md`
- Create: `.claude/commands/snapshot.md`
- Create: `.claude/commands/dotfiles.md`
- Create: `.claude/commands/pair.md`
- Create: `.claude/commands/harness-check.md`

**Interfaces:**
- Consumes: Automation scripts in `scripts/`.
- Produces: Standardized Claude Code slash command markdown wrappers.

- [ ] **Step 1: Implement `scripts/dotfiles_sync.sh`**

```bash
#!/usr/bin/env bash
# scripts/dotfiles_sync.sh - Pillar 4 State Protection & Dotfile Diff/Sync
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
                cp -v "${HOME}/${f}" "${BACKUP_TARGET}/${f}"
            fi
        done
        echo "Backup complete in ${BACKUP_TARGET}"
        ;;
    diff)
        echo "=== Dotfiles Diff Inspection ==="
        for f in "${FILES_TO_MANAGE[@]}"; do
            if [ -f "${BACKUP_TARGET}/${f}" ] && [ -f "${HOME}/${f}" ]; then
                echo "--- Diff for ~/${f} ---"
                diff -u "${BACKUP_TARGET}/${f}" "${HOME}/${f}" || true
            elif [ -f "${HOME}/${f}" ]; then
                echo "File ~/${f} exists but has no backup in repository."
            fi
        done
        ;;
    restore)
        echo "=== Restoring Dotfiles ==="
        for f in "${FILES_TO_MANAGE[@]}"; do
            if [ -f "${BACKUP_TARGET}/${f}" ]; then
                cp -iv "${BACKUP_TARGET}/${f}" "${HOME}/${f}"
            fi
        done
        ;;
    *)
        echo "Usage: $0 {backup|diff|restore}"
        exit 1
        ;;
esac
```

- [ ] **Step 2: Make executable and test backup/diff functionality**

Run: `chmod +x scripts/dotfiles_sync.sh && ./scripts/dotfiles_sync.sh backup`
Expected: Backup files copied to `backups/dotfiles/`.

- [ ] **Step 3: Create `.claude/commands/` markdown wrappers**

Create:
- `.claude/commands/diag.md`
- `.claude/commands/clean.md`
- `.claude/commands/upgrade.md`
- `.claude/commands/snapshot.md`
- `.claude/commands/dotfiles.md`
- `.claude/commands/pair.md`
- `.claude/commands/harness-check.md`

Each markdown defines the tool invocation, flags, and behavioral constraints.

- [ ] **Step 4: Commit slash commands and dotfiles synchronizer**

```bash
git add scripts/dotfiles_sync.sh .claude/commands/ backups/dotfiles/
git commit -m "feat(commands): implement custom slash commands suite and dotfiles sync engine

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: Custom Subagents Registry (`.claude/agents/*.md`)

**Files:**
- Create: `.claude/agents/security-auditor.md`
- Create: `.claude/agents/system-operator.md`

**Interfaces:**
- Consumes: Claude Code custom subagent schema with frontmatter (`name`, `description`, `tools`, `model`, `isolation`).
- Produces: Declarative subagent personas for security audits and isolated worktree operations.

- [ ] **Step 1: Implement `.claude/agents/security-auditor.md`**

```markdown
---
name: security-auditor
description: Specialized read-only security auditor for vulnerability, secret leakage, and permission analysis.
tools:
  - Read
  - Grep
  - Glob
  - Bash
model: sonnet
effort: high
---

You are a read-only security auditor for `os-manager`.
You review code and configurations for:
1. Hardcoded secrets, API tokens, and credentials.
2. Insecure shell scripting patterns (unquoted expansions, eval vulnerabilities).
3. Violations of WSL2 ext4 vs Windows 9P filesystem isolation rules.
4. Tier 3 security invariant hazards.

You never modify code directly. You provide structured audit reports and actionable remediation advice.
```

- [ ] **Step 2: Implement `.claude/agents/system-operator.md`**

```markdown
---
name: system-operator
description: System automation and script maintenance operator running with git worktree isolation.
tools:
  - Bash
  - Read
  - Grep
  - Glob
  - Edit
  - Write
isolation: worktree
effort: high
---

You are a systems operations engineer executing system automation and maintenance tasks for `os-manager`.
All your refactoring work takes place within isolated git worktrees.
You strictly adhere to:
1. POSIX / Bash 5+ syntax with `set -euo pipefail`.
2. Safe cleanup and maintenance rules defined in `.claude/rules/`.
3. Auto-healing linting verification before submitting changes.
```

- [ ] **Step 3: Commit subagent configurations**

```bash
git add .claude/agents/
git commit -m "feat(agents): register security-auditor and system-operator custom subagents

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Modular Rules Invariants (`.claude/rules/*.md`)

**Files:**
- Create: `.claude/rules/wsl-boundaries.md`
- Create: `.claude/rules/safety-tiers.md`
- Create: `.claude/rules/error-recovery.md`

**Interfaces:**
- Consumes: Architectural boundary requirements from specifications.
- Produces: Modular system prompt rules loaded into every Claude Code session.

- [ ] **Step 1: Implement `.claude/rules/wsl-boundaries.md`**

```markdown
# WSL2 Filesystem Boundaries & Storage Invariants

1. **Native ext4 Performance Domain (`/home/rizz/`)**:
   - All Git repositories, Node `node_modules`, Python virtualenvs (`.venv`), temporary build artifacts, and package stores MUST reside on the native ext4 Linux partition (`/home/rizz/`).
   - Never initialize high I/O developer workspaces on Windows mounts (`/mnt/c/`, `/mnt/d/`) due to 9P file system virtualization latency.

2. **NTFS Mount Access Rules (`/mnt/c/`, `/mnt/d/`)**:
   - `/mnt/d/`: Designated solely for compressed WSL point-in-time snapshots and offsite archival.
   - `/mnt/c/`: Read-only host inspection. Direct writes or edits to `/mnt/c/Windows`, `Program Files`, or `AppData` are strictly forbidden.
```

- [ ] **Step 2: Implement `.claude/rules/safety-tiers.md`**

```markdown
# Safety Tiers & Action Classification

1. **Tier 0 (Autonomous Read-Only)**:
   - System state inspection (`free`, `df`, `systemctl status`, `git status`, `ps`, read-only diagnostics) may run autonomously without friction.

2. **Tier 1 (Workspace Contained)**:
   - Modifications inside `/home/rizz/dev/os-manager/` are safe and autonomous, subject to post-tool linting.

3. **Tier 2 (Controlled System Operations)**:
   - Standard maintenance scripts (`sys_diag.sh`, `clean_system.sh`, `update_runtimes.sh`, `wsl_snapshot.sh`) are authorized.

4. **Tier 3 (Strict Invariant Violations - Hard Blocked)**:
   - Deletions of `/` or `~`, WSL termination commands (`wsl --unregister`), wildcard package purges (`apt purge *`), and direct disk formatting (`mkfs.*`) are blocked deterministically.
```

- [ ] **Step 3: Implement `.claude/rules/error-recovery.md`**

```markdown
# Error Recovery & Auto-Healing Protocol

1. **Closed-Loop Auto-Healing**:
   - When a hook interrupts a tool execution with Exit Code 2, read the diagnostic output on `stderr` and perform an immediate repair turn.
   - For syntax errors (`bash -n`, `jq`, `python3 -m py_compile`), inspect the specific line mentioned in `stderr` and apply the fix.

2. **Graceful Degradation**:
   - If optional developer tools (e.g., `shellcheck`, `shfmt`) are absent, fall back to core bash and python built-in syntax validators.
```

- [ ] **Step 4: Commit modular rules**

```bash
git add .claude/rules/
git commit -m "feat(rules): add modular rules for WSL boundaries, safety tiers, and error recovery

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Multi-Agent SSOT Bridge & Self-Test Diagnostic Suite (`scripts/sync_agent_skills.sh`, `scripts/harness_check.sh`)

**Files:**
- Create: `scripts/sync_agent_skills.sh`
- Create: `scripts/harness_check.sh`
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: Master skills in `.claude/skills/`.
- Produces: Relative symlinks in `.agents/skills/`, absolute symlinks in `~/.gemini/config/skills/`, and end-to-end self-diagnostic verification report.

- [ ] **Step 1: Implement `scripts/sync_agent_skills.sh`**

```bash
#!/usr/bin/env bash
# scripts/sync_agent_skills.sh - Multi-Agent Single Source of Truth (SSOT) Symlink Bridge
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_SKILLS="${WORKSPACE_ROOT}/.claude/skills"
UNIVERSAL_SKILLS="${WORKSPACE_ROOT}/.agents/skills"
ANTIGRAVITY_SKILLS="${HOME}/.gemini/config/skills"

mkdir -p "${UNIVERSAL_SKILLS}"
mkdir -p "${ANTIGRAVITY_SKILLS}"

echo "=== Synchronizing Multi-Agent Skills (SSOT: .claude/skills) ==="

# 1. Clean broken symlinks in targets
find "${UNIVERSAL_SKILLS}" -xtype l -delete
find "${ANTIGRAVITY_SKILLS}" -xtype l -delete

# 2. Propagate to Universal Agent standard (.agents/skills/) using relative symlinks
for skill_path in "${CLAUDE_SKILLS}"/*; do
    if [ -d "${skill_path}" ]; then
        skill_name="$(basename "${skill_path}")"
        # Relative link: ../../.claude/skills/<name>
        ln -sfn "../../.claude/skills/${skill_name}" "${UNIVERSAL_SKILLS}/${skill_name}"
    fi
done

# 3. Propagate to Google Antigravity (~/.gemini/config/skills/) using absolute symlinks
for skill_path in "${CLAUDE_SKILLS}"/*; do
    if [ -d "${skill_path}" ]; then
        skill_name="$(basename "${skill_path}")"
        ln -sfn "${skill_path}" "${ANTIGRAVITY_SKILLS}/${skill_name}"
    fi
done

echo "✓ Synchronized $(ls -1 "${UNIVERSAL_SKILLS}" | wc -l) skills to .agents/skills/ (Universal Agent)"
echo "✓ Synchronized $(ls -1 "${ANTIGRAVITY_SKILLS}" | wc -l) skills to ~/.gemini/config/skills/ (Google Antigravity)"
```

- [ ] **Step 2: Implement `scripts/harness_check.sh`**

```bash
#!/usr/bin/env bash
# scripts/harness_check.sh - End-to-end self-diagnostic verification matrix
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=================================================="
echo "      os-manager Claude Harness Self-Check        "
echo "=================================================="

# 1. Run unit test suite
echo "1. Running Hook & Guardrail Test Suite..."
"${WORKSPACE_ROOT}/tests/test_harness.sh"

# 2. Validate Multi-Agent Sync
echo "2. Validating Multi-Agent Skill Symlinks..."
"${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh"

# 3. Validate Settings JSON syntax
echo "3. Validating .claude/settings.json configuration..."
jq empty "${WORKSPACE_ROOT}/.claude/settings.json"
echo "   [PASS] Settings configuration valid."

echo "=================================================="
echo "✓ ALL HARNESS COMPONENT CHECKS PASSED"
echo "=================================================="
```

- [ ] **Step 3: Make executable and run harness check**

Run: `chmod +x scripts/sync_agent_skills.sh scripts/harness_check.sh && ./scripts/harness_check.sh`
Expected: ALL HARNESS COMPONENT CHECKS PASSED.

- [ ] **Step 4: Commit multi-agent bridge and self-test suite**

```bash
git add scripts/sync_agent_skills.sh scripts/harness_check.sh .agents/
git commit -m "feat(interop): implement Multi-Agent SSOT skill bridge and harness self-check suite

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: Governance Integration, CLAUDE.md Update & Push to GitHub

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: All completed harness deliverables.
- Produces: Updated `CLAUDE.md` documenting new slash commands, rules, hooks, and git synchronization with GitHub.

- [ ] **Step 1: Update `CLAUDE.md` with Harness Architecture & Commands**

Incorporate references to:
- Custom Slash Commands: `/diag`, `/clean`, `/upgrade`, `/snapshot`, `/dotfiles`, `/pair`, `/harness-check`.
- Lifecycle Hooks and Auto-Healing Linter.
- 4-Tier Security Matrix and WSL2 Filesystem Boundaries.
- Multi-Agent SSOT Symlink Bridge.

- [ ] **Step 2: Run complete harness self-check**

Run: `./scripts/harness_check.sh`
Expected: PASS.

- [ ] **Step 3: Commit and push changes to remote GitHub repository**

```bash
git add CLAUDE.md
git commit -m "docs(governance): update CLAUDE.md with full Claude Harness architecture and slash commands

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git push origin main
```

---
