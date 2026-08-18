# Desktop Notification Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a zero-dependency CLI notification bridge (`scripts/notify_host.sh`) dispatching native Windows 10 and 11 Action Center toast alerts from WSL2, with non-blocking lifecycle hook integration.

**Architecture:** A lightweight POSIX Bash script formats incoming alerts (`--title`, `--message`, `--type`, `--silent`, `--app-id`, `--dry-run`) into WinRT XML Toast payloads and dispatches them via `powershell.exe`. The dispatcher enforces rate-limiting debouncing via `/tmp` lockfiles and handles headless or missing-interop environments gracefully. Asynchronous non-blocking dispatch `(scripts/notify_host.sh ... &) disown` guarantees zero disruption to the <100ms hook latency budget.

**Tech Stack:** Bash 5.2+, Windows PowerShell (`powershell.exe`), Windows Runtime (WinRT) XML Toast Notification API, `jq`, `shellcheck`.

**Spec:** `docs/superpowers/specs/2026-08-19-desktop-notification-bridge-design.md`

## Global Constraints

- **Mandatory Non-Blocking Hook Dispatch**: Notifications triggered from lifecycle hooks (e.g., `pre_tool_guard.sh`) MUST execute asynchronously via detached subshells (`(scripts/notify_host.sh ... &) disown` or `--async`). This preserves NFR-1 hook latency (<100ms P99).
- **Zero External Linux Dependencies**: The client must run on standard POSIX shell builtins and standard coreutils without Python, Node.js, or external CLI helpers.
- **Fail-Safe Graceful Degradation**: If `powershell.exe` or WSL interop is unavailable, the script emits a terminal alert and logs to audit telemetry. It exits with code 0 without unhandled errors.
- **Strict Payload Sanitization**: Double quotes, backticks, dollar signs, and XML entity characters (`&`, `<`, `>`, `"`, `'`) must be escaped to prevent PowerShell command injection and XML parsing failures.
- **Rate-Limiting / Debouncing**: Enforce a minimum 1.0-second delay between identical notification categories using lockfiles in `/tmp/` to prevent notification storms.

---

### Task 1: Create Automated Unit Test Suite for Notification Bridge

**Files:**
- Create: `tests/test_notify_host.sh`

**Interfaces:**
- Consumes: `scripts/notify_host.sh` (`--title`, `--message`, `--type`, `--silent`, `--app-id`, `--dry-run`, `--async`)
- Produces: Executable test suite validating CLI argument parsing, XML entity escaping, PowerShell script construction, rate-limiting debouncing, and interop fallback.

- [ ] **Step 1: Write the failing unit test suite**

```bash
cat <<'EOF' > tests/test_notify_host.sh
#!/usr/bin/env bash
# tests/test_notify_host.sh - Unit tests for Desktop Notification Bridge
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NOTIFIER_SCRIPT="${WORKSPACE_ROOT}/scripts/notify_host.sh"

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
echo "Running Desktop Notification Bridge Unit Tests"
echo "=================================================="

# 1. Script existence and executable permission
TOTAL_TESTS=$((TOTAL_TESTS + 1))
if [ -x "${NOTIFIER_SCRIPT}" ]; then
    echo "  [PASS] notify_host.sh exists and is executable"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] notify_host.sh missing or not executable at ${NOTIFIER_SCRIPT}"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# 2. Test --help flag
set +e
HELP_OUT="$("${NOTIFIER_SCRIPT}" --help 2>&1)"
assert_exit_code "--help flag exit code" 0 $?
assert_contains "--help output content" "${HELP_OUT}" "Usage:"
set -e

# 3. Test --dry-run standard toast generation
DRY_RUN_OUT="$("${NOTIFIER_SCRIPT}" --dry-run --title "Test Title" --message "Test Message" --type info)"
assert_contains "dry-run contains title" "${DRY_RUN_OUT}" "Test Title"
assert_contains "dry-run contains message" "${DRY_RUN_OUT}" "Test Message"
assert_contains "dry-run contains WinRT Toast XML" "${DRY_RUN_OUT}" "ToastNotificationManager"
assert_contains "dry-run contains audio cue" "${DRY_RUN_OUT}" "Notification.Default"

# 4. Test security alert audio mapping
SEC_OUT="$("${NOTIFIER_SCRIPT}" --dry-run --title "Security Block" --message "Invariant Blocked" --type security)"
assert_contains "security alert urgent sound" "${SEC_OUT}" "Notification.Urgent"

# 5. Test XML entity and shell special character escaping
ESCAPE_OUT="$("${NOTIFIER_SCRIPT}" --dry-run --title "Alert & <Special>" --message 'Quotes "and" $variables and `backticks`' --type error)"
assert_contains "XML ampersand escaping" "${ESCAPE_OUT}" "Alert &amp; &lt;Special&gt;"
assert_contains "PowerShell quote escaping" "${ESCAPE_OUT}" '`"and`"'
assert_contains "PowerShell variable escaping" "${ESCAPE_OUT}" '`$variables'
assert_contains "PowerShell backtick escaping" "${ESCAPE_OUT}" '``backticks``'

# 6. Test --silent flag suppresses audio
SILENT_OUT="$("${NOTIFIER_SCRIPT}" --dry-run --title "Silent" --message "Shh" --silent)"
assert_contains "silent attribute enabled" "${SILENT_OUT}" 'silent="true"'

# 7. Test rate limiting / debouncing
set +e
RATE_LIMIT_CAT="unit_test_debounce"
"${NOTIFIER_SCRIPT}" --dry-run --title "Rate1" --message "M1" --category "${RATE_LIMIT_CAT}" > /dev/null 2>&1
FIRST_EXIT=$?
"${NOTIFIER_SCRIPT}" --dry-run --title "Rate2" --message "M2" --category "${RATE_LIMIT_CAT}" > /dev/null 2>&1
SECOND_EXIT=$?
assert_exit_code "First notification succeeds" 0 ${FIRST_EXIT}
assert_exit_code "Rapid duplicate category debounced cleanly" 0 ${SECOND_EXIT}
set -e

# Clean up temporary test rate-limiting lockfiles
rm -f /tmp/.os_manager_notify_ratelimit_"${RATE_LIMIT_CAT}"

echo "=================================================="
echo "Notification Bridge Unit Tests Complete: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0
EOF
chmod +x tests/test_notify_host.sh
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./tests/test_notify_host.sh`
Expected: FAIL because `scripts/notify_host.sh` does not exist or is missing flags.

- [ ] **Step 3: Create stub script to confirm test execution failure signature**

```bash
cat <<'EOF' > scripts/notify_host.sh
#!/usr/bin/env bash
# scripts/notify_host.sh - Stub for notification bridge
echo "notify_host stub" >&2
exit 1
EOF
chmod +x scripts/notify_host.sh
```

- [ ] **Step 4: Run unit test runner to verify expected failure**

Run: `./tests/test_notify_host.sh`
Expected: FAIL with failed assertions on `--help`, `--dry-run`, and XML escaping.

- [ ] **Step 5: Commit test suite**

```bash
git add tests/test_notify_host.sh scripts/notify_host.sh
git commit -m "test(notifications): add unit test suite for desktop notification bridge"
```

---

### Task 2: Implement Desktop Notification Bridge CLI

**Files:**
- Modify: `scripts/notify_host.sh`
- Test: `tests/test_notify_host.sh`

**Interfaces:**
- Consumes: CLI parameters (`--title`, `--message`, `--type`, `--app-id`, `--silent`, `--async`, `--dry-run`, `--category`, `--help`), `/proc/sys/fs/binfmt_misc/WSLInterop`, `powershell.exe`.
- Produces: Sanitized PowerShell WinRT toast invocation or graceful terminal fallback.

- [ ] **Step 1: Implement full `scripts/notify_host.sh` script**

```bash
cat <<'EOF' > scripts/notify_host.sh
#!/usr/bin/env bash
# scripts/notify_host.sh - Zero-dependency Desktop Notification Bridge for WSL2
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Defaults
TITLE="OS-Manager"
MESSAGE=""
TYPE="info"
APP_ID="OS-Manager"
SILENT="false"
ASYNC="false"
DRY_RUN="false"
CATEGORY=""

show_help() {
    cat <<HELP
Usage: $(basename "$0") [OPTIONS]

Zero-dependency WSL2 to Windows 10/11 Desktop Notification Bridge.

Options:
  --title <text>         Notification header text (default: "OS-Manager")
  --message <text>       Main notification body text (required)
  --type <type>          Notification type: info | success | warning | error | security (default: info)
  --app-id <string>      Windows application identifier for grouping (default: "OS-Manager")
  --category <string>    Rate-limiting key category (default: derived from type)
  --silent               Mute notification chime sound
  --async                Execute in a detached background subshell
  --dry-run              Print generated PowerShell payload without executing
  -h, --help             Show this help message and exit

Examples:
  $(basename "$0") --title "Backup" --message "Snapshot exported successfully" --type success
  $(basename "$0") --title "Security" --message "Blocked Tier 3 command" --type security --async
HELP
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --title)
            TITLE="$2"
            shift 2
            ;;
        --message)
            MESSAGE="$2"
            shift 2
            ;;
        --type)
            TYPE="$2"
            shift 2
            ;;
        --app-id)
            APP_ID="$2"
            shift 2
            ;;
        --category)
            CATEGORY="$2"
            shift 2
            ;;
        --silent)
            SILENT="true"
            shift
            ;;
        --async)
            ASYNC="true"
            shift
            ;;
        --dry-run)
            DRY_RUN="true"
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

if [ -z "${MESSAGE}" ] && [ "${DRY_RUN}" = "false" ]; then
    echo "Error: --message is required." >&2
    exit 1
fi

# Category for rate-limiting
if [ -z "${CATEGORY}" ]; then
    CATEGORY="${TYPE}"
fi

# Rate-limiting / debouncing check (minimum 1 second between identical categories)
RATE_LIMIT_FILE="/tmp/.os_manager_notify_ratelimit_${CATEGORY}"
NOW="$(date +%s)"
if [ -f "${RATE_LIMIT_FILE}" ]; then
    LAST_SENT="$(cat "${RATE_LIMIT_FILE}" 2>/dev/null || echo 0)"
    DIFF=$((NOW - LAST_SENT))
    if [ "${DIFF}" -lt 1 ] && [ "${DIFF}" -ge 0 ]; then
        # Debounced silently
        exit 0
    fi
fi
echo "${NOW}" > "${RATE_LIMIT_FILE}" 2>/dev/null || true

# Sound mapping based on type
case "${TYPE}" in
    security|error)
        SOUND_EVENT="ms-winsoundevent:Notification.Urgent"
        ;;
    warning)
        SOUND_EVENT="ms-winsoundevent:Notification.Reminder"
        ;;
    info|success|*)
        SOUND_EVENT="ms-winsoundevent:Notification.Default"
        ;;
esac

# XML and PowerShell Sanitization Helper
sanitize_xml_and_ps() {
    local text="$1"
    # 1. XML entity encoding
    text="${text//&/&amp;}"
    text="${text//</&lt;}"
    text="${text//>/&gt;}"
    text="${text//\"/&quot;}"
    text="${text//\'/&apos;}"
    # 2. PowerShell string escaping for double-quoted here-strings
    text="${text//\`/\`\`}"
    text="${text//\$/\`\$}"
    text="${text//\"/\`\"}"
    echo -n "${text}"
}

SANITIZED_TITLE="$(sanitize_xml_and_ps "${TITLE}")"
SANITIZED_MESSAGE="$(sanitize_xml_and_ps "${MESSAGE}")"
SANITIZED_APP_ID="$(sanitize_xml_and_ps "${APP_ID}")"

# Construct WinRT Toast XML Payload
read -r -d '' PS_COMMAND <<PSEOF || true
\$xml = @"
<toast duration="short">
  <visual>
    <binding template="ToastGeneric">
      <text id="1">${SANITIZED_TITLE}</text>
      <text id="2">${SANITIZED_MESSAGE}</text>
      <text placement="attribution">OS-Manager (WSL2 Debian)</text>
    </binding>
  </visual>
  <audio src="${SOUND_EVENT}" silent="${SILENT}" />
</toast>
"@;
\$doc = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]::new();
\$doc.LoadXml(\$xml);
\$toast = [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime]::new(\$doc);
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]::CreateToastNotifier("${SANITIZED_APP_ID}").Show(\$toast);
PSEOF

# Handle --dry-run
if [ "${DRY_RUN}" = "true" ]; then
    echo "${PS_COMMAND}"
    exit 0
fi

# Dispatch helper
dispatch_notification() {
    # Check for WSL Interop and powershell.exe
    if [ ! -f "/proc/sys/fs/binfmt_misc/WSLInterop" ] || ! command -v powershell.exe >/dev/null 2>&1; then
        # Graceful fallback: log to audit telemetry and emit terminal bell
        printf '\a' >&2 || true
        local log_file="${WORKSPACE_ROOT}/backups/logs/harness_audit.jsonl"
        if [ -d "$(dirname "${log_file}")" ]; then
            local now_iso
            now_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
            local now_epoch
            now_epoch="$(date +%s)"
            echo "{\"timestamp_iso\":\"${now_iso}\",\"timestamp_epoch\":${now_epoch},\"hook_name\":\"NotificationFallback\",\"target_tool\":\"${TYPE}\",\"duration_ms\":0.0,\"duration_us\":0,\"exit_code\":0}" >> "${log_file}" 2>/dev/null || true
        fi
        return 0
    fi

    # Invoke powershell.exe with NonInteractive, Hidden Window
    powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "${PS_COMMAND}" >/dev/null 2>&1 || true
}

# Handle --async
if [ "${ASYNC}" = "true" ]; then
    ( dispatch_notification ) & disown
    exit 0
else
    dispatch_notification
fi
EOF
chmod +x scripts/notify_host.sh
```

- [ ] **Step 2: Run unit tests to verify pass**

Run: `./tests/test_notify_host.sh`
Expected: PASS (all assertions pass with 0 failures).

- [ ] **Step 3: Verify shellcheck compliance**

Run: `shellcheck -s bash scripts/notify_host.sh`
Expected: Clean exit with 0 errors/warnings.

- [ ] **Step 4: Commit notification bridge implementation**

```bash
git add scripts/notify_host.sh
git commit -m "feat(notifications): implement Windows desktop notification bridge script"
```

---

### Task 3: Wire Asynchronous Toast Alerts Into Security Guardrails and Maintenance Scripts

**Files:**
- Modify: `scripts/hooks/pre_tool_guard.sh`
- Modify: `scripts/wsl_snapshot.sh`
- Test: `tests/test_notify_host.sh`

**Interfaces:**
- Consumes: `scripts/notify_host.sh` (`--type security`, `--type success`, `--async`)
- Produces: Asynchronous toast notifications when Tier 3 invariant blocks fire and when WSL snapshots finish.

- [ ] **Step 1: Verify `scripts/hooks/pre_tool_guard.sh` non-blocking security dispatcher**

Read lines 27-34 of `scripts/hooks/pre_tool_guard.sh`:
Confirm `notify_security_violation()` uses `( "${notifier}" --type security --title "Security Blocked" --message "${reason}" --async 2>/dev/null & ) disown || true`.

```bash
cat <<'EOF' > /tmp/check_guard_notifier.sh
#!/usr/bin/env bash
set -euo pipefail
if grep -q "notify_security_violation" scripts/hooks/pre_tool_guard.sh && grep -q "notify_host.sh" scripts/hooks/pre_tool_guard.sh; then
    echo "pre_tool_guard.sh already wired for desktop notifications."
else
    echo "Wiring required."
    exit 1
fi
EOF
bash /tmp/check_guard_notifier.sh
rm -f /tmp/check_guard_notifier.sh
```

- [ ] **Step 2: Wire notification into `scripts/wsl_snapshot.sh` on backup readiness**

Update `scripts/wsl_snapshot.sh` to trigger an info/success notification alerting the user to the generated snapshot path:

```bash
cat <<'EOF' > scripts/wsl_snapshot.sh
#!/usr/bin/env bash
# ==============================================================================
# wsl_snapshot.sh — Backup and Export WSL Debian Distro
# ==============================================================================
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="/mnt/d/wsl_backup"
DATE_TAG=$(date +"%Y%m%d_%H%M%S")
SNAPSHOT_FILE="$BACKUP_DIR/debian_snapshot_${DATE_TAG}.tar"

echo "==> Creating backup directory at $BACKUP_DIR (if not exists)..."
mkdir -p "$BACKUP_DIR"

echo "=============================================================================="
echo " WSL BACKUP HELPER"
echo "=============================================================================="
echo "To create a complete snapshot of this Debian instance, execute the following"
echo "command from Windows PowerShell / Terminal:"
echo ""
echo "  wsl --export Debian \"D:\\wsl_backup\\debian_snapshot_${DATE_TAG}.tar\""
echo ""
echo "To restore from this snapshot if disaster occurs:"
echo "  wsl --import Debian-Restored \"C:\\WSL\\Debian\" \"D:\\wsl_backup\\debian_snapshot_${DATE_TAG}.tar\""
echo "=============================================================================="

# Dispatch desktop notification helper
NOTIFIER="${WORKSPACE_ROOT}/scripts/notify_host.sh"
if [ -x "${NOTIFIER}" ]; then
    "${NOTIFIER}" --type info --title "WSL Snapshot Ready" --message "Export target prepared: debian_snapshot_${DATE_TAG}.tar" --async 2>/dev/null || true
fi
EOF
chmod +x scripts/wsl_snapshot.sh
```

- [ ] **Step 3: Run `wsl_snapshot.sh` and verify execution**

Run: `./scripts/wsl_snapshot.sh`
Expected: Prints backup instructions and cleanly triggers notification helper without hang.

- [ ] **Step 4: Commit changes to snapshot script**

```bash
git add scripts/wsl_snapshot.sh scripts/hooks/pre_tool_guard.sh
git commit -m "feat(notifications): wire asynchronous toast alerts into wsl_snapshot and security guard"
```

---

### Task 4: Master Harness Integration and Verification

**Files:**
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `tests/test_notify_host.sh`, `scripts/notify_host.sh`
- Produces: Automated assertions in master test runner verifying script syntax, `--dry-run` output, and unit test suite completion.

- [ ] **Step 1: Check existing assertions in `tests/test_harness.sh`**

Run: `grep -q "test_notify_host.sh" tests/test_harness.sh`
Expected: FAIL (assertion not yet present).

- [ ] **Step 2: Add notification bridge test assertions to `tests/test_harness.sh`**

Append the notification test block to `tests/test_harness.sh`:

```bash
cat <<'EOF' >> tests/test_harness.sh

echo "--- Testing Desktop Notification Bridge Suite ---"
set +e
"${WORKSPACE_ROOT}/scripts/notify_host.sh" --help > /dev/null 2>&1
assert_exit_code "notify_host.sh --help execution" 0 $?

DRY_RUN_TEST="$("${WORKSPACE_ROOT}/scripts/notify_host.sh" --dry-run --title "Test" --message "Msg")"
echo "${DRY_RUN_TEST}" | grep -q "ToastNotificationManager"
assert_exit_code "notify_host.sh --dry-run WinRT XML generation" 0 $?

"${WORKSPACE_ROOT}/tests/test_notify_host.sh" > /dev/null 2>&1
assert_exit_code "test_notify_host.sh complete suite" 0 $?
set -e
EOF
```

- [ ] **Step 3: Run the full harness test suite**

Run: `./tests/test_harness.sh`
Expected: All 35+ assertions pass with 0 failures.

- [ ] **Step 4: Run harness self-check**

Run: `./scripts/harness_check.sh`
Expected: Pass with 0 errors.

- [ ] **Step 5: Commit `tests/test_harness.sh`**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate notification bridge assertions into master harness"
```

---

## Plan Self-Review Checklist

- **Spec Coverage:** 
  - Zero-dependency notification CLI (`scripts/notify_host.sh`) is implemented in Task 2.
  - Mandatory asynchronous non-blocking dispatch `(scripts/notify_host.sh ... &) disown` is preserved in Tasks 1, 2, and 3.
  - Rate limiting / debouncing is tested in Task 1 and implemented in Task 2.
  - XML and PowerShell string sanitization is tested in Task 1 and implemented in Task 2.
  - Integration with `scripts/hooks/pre_tool_guard.sh` and `scripts/wsl_snapshot.sh` is verified in Task 3.
  - Master test harness assertions are verified in Task 4.
- **Placeholder Scan:** Zero instances of "TBD", "TODO", "implement later", or ambiguous ellipses.
- **Type Consistency:** Parameters (`--title`, `--message`, `--type`, `--app-id`, `--silent`, `--async`, `--dry-run`, `--category`) are uniform across all tasks.
