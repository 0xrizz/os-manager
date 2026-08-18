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

# Rate-limiting / debouncing check (minimum 1 second between identical categories, skipped during --dry-run)
if [ "${DRY_RUN}" = "false" ]; then
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
fi

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
    # shellcheck disable=SC2016
    python3 -c '
import html, sys
text = sys.argv[1]
# 1. XML entity encoding
text = html.escape(text, quote=True).replace("\x27", "&apos;")
# 2. PowerShell string escaping for double-quoted here-strings
text = text.replace("`", "``").replace("$", "`$").replace("\"", "`\"")
sys.stdout.write(text)
' "$1"
}

SANITIZED_TITLE="$(sanitize_xml_and_ps "${TITLE}")"
SANITIZED_MESSAGE="$(sanitize_xml_and_ps "${MESSAGE}")"
SANITIZED_APP_ID="$(sanitize_xml_and_ps "${APP_ID}")"

# Construct WinRT Toast XML Payload
PS_COMMAND=$(cat <<PSEOF
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
)

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
