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

# Tier 3 Block: APT Wildcard Purge
PAYLOAD_TIER3_APT='{"tool_name":"Bash","tool_input":{"command":"apt purge *"}}'
echo "${PAYLOAD_TIER3_APT}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (apt purge *)" 2 $?

# Tier 3 Block: Pacman Wildcard Removal
PAYLOAD_TIER3_PACMAN='{"tool_name":"Bash","tool_input":{"command":"pacman -Rcs *"}}'
echo "${PAYLOAD_TIER3_PACMAN}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (pacman -Rcs *)" 2 $?

# Tier 3 Block: DNF Mass Removal
PAYLOAD_TIER3_DNF='{"tool_name":"Bash","tool_input":{"command":"dnf remove --all"}}'
echo "${PAYLOAD_TIER3_DNF}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (dnf remove --all)" 2 $?

# Tier 3 Block: Zypper Wildcard Removal
PAYLOAD_TIER3_ZYPPER='{"tool_name":"Bash","tool_input":{"command":"zypper remove *"}}'
echo "${PAYLOAD_TIER3_ZYPPER}" | "${HOOKS_DIR}/pre_tool_guard.sh" > /dev/null 2>&1
assert_exit_code "Tier 3 Block (zypper remove *)" 2 $?

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

echo "--- Testing Cross-Distribution Discovery Unit Suite ---"
"${WORKSPACE_ROOT}/tests/test_distro.sh" > /dev/null 2>&1
assert_exit_code "test_distro.sh complete suite" 0 $?
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

echo "--- Testing Prometheus Metrics Exporter Suite ---"
python3 -m py_compile "${WORKSPACE_ROOT}/scripts/metrics_exporter.py" > /dev/null 2>&1
assert_exit_code "metrics_exporter.py bytecode compilation" 0 $?

"${WORKSPACE_ROOT}/scripts/metrics_exporter.py" --help > /dev/null 2>&1
assert_exit_code "metrics_exporter.py --help execution" 0 $?

python3 -m unittest "${WORKSPACE_ROOT}/tests/test_metrics_exporter.py" > /dev/null 2>&1
assert_exit_code "test_metrics_exporter.py unit test suite" 0 $?

[ -f "${WORKSPACE_ROOT}/systemd/os-metrics-exporter.service" ] && SERVICE_EXISTS=0 || SERVICE_EXISTS=1
assert_exit_code "os-metrics-exporter.service exists" 0 "${SERVICE_EXISTS}"

echo "--- Testing Desktop Notification Bridge Suite ---"
"${WORKSPACE_ROOT}/scripts/notify_host.sh" --help > /dev/null 2>&1
assert_exit_code "notify_host.sh --help execution" 0 $?

DRY_RUN_TEST="$("${WORKSPACE_ROOT}/scripts/notify_host.sh" --dry-run --title "Test" --message "Msg")"
echo "${DRY_RUN_TEST}" | grep -q "ToastNotificationManager"
assert_exit_code "notify_host.sh --dry-run WinRT XML generation" 0 $?

"${WORKSPACE_ROOT}/tests/test_notify_host.sh" > /dev/null 2>&1
assert_exit_code "test_notify_host.sh complete suite" 0 $?
set -e

echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
