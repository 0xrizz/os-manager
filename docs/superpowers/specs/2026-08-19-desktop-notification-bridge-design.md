# Technical Design Specification: Desktop Notification Bridge (Deliverable 3.3)

## 1. Executive Summary and Objective

This document defines the technical specification for the **Desktop Notification Bridge** (Deliverable 3.3 from `docs/PRD.md`).

Long-running maintenance tasks, disaster recovery snapshots, and security invariant violations inside WSL2 require real-time visibility on the Windows desktop. To solve this, the Desktop Notification Bridge provides a zero-dependency notification client (`scripts/notify_host.sh`) that dispatches native Windows 10 and Windows 11 Action Center toast notifications from WSL2. To protect Non-Functional Requirement 1 (NFR-1: <100ms latency), all notifications triggered from lifecycle hooks (such as Tier 3 blocks in `pre_tool_guard.sh`) MUST be dispatched asynchronously in the background via `(scripts/notify_host.sh ... &) disown`.

---

## 2. System Architecture and Component Interaction

```text
 ══════════════════════════════════════════════════════════════════════════════════════════════════
                         DESKTOP NOTIFICATION BRIDGE ARCHITECTURE
 ══════════════════════════════════════════════════════════════════════════════════════════════════

 ┌──────────────────────────────────────────────────────────────────────────────────────────────┐
 │ WSL2 EVENT EMITTERS & LIFECYCLE HOOKS                                                        │
 │ • `scripts/hooks/pre_tool_guard.sh` (Dispatched via `(scripts/notify_host.sh ... &) disown`) │
 │ • `scripts/clean_system.sh` (Storage Reclamation Complete)                                   │
 │ • `scripts/wsl_snapshot.sh` (Distro Snapshot Export Complete)                                │
 │ • `scripts/compact_host_disk.sh` (Host Disk Compaction Complete)                             │
 └──────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                │
 ┌──────────────────────────────────────────────▼───────────────────────────────────────────────┐
 │ NOTIFICATION CLIENT (`scripts/notify_host.sh`)                                               │
 │ • Validates input arguments (`--title`, `--message`, `--type`, `--silent`)                   │
 │ • Sanitizes string payloads against shell & PowerShell injection                             │
 │ • Evaluates rate-limiting cache in `/tmp/.os_manager_notify_ratelimit_*`                     │
 └──────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                │
        ┌───────────────────────────────────────┴───────────────────────────────────────┐
        │ [Windows Interop Available & Enabled]                                         │ [Interop Disabled / Headless]
        ▼                                                                               ▼
 ┌──────────────────────────────────────────────┐                       ┌──────────────────────────────────────────────┐
 │ POWERSHELL WINRT TOAST RUNNER                │                       │ FALLBACK CHANNEL                             │
 │ • Invokes `powershell.exe` in background     │                       │ • Emits terminal bell (`\a`)                 │
 │ • Instantiates WinRT XML Toast Template      │                       │ • Logs message to audit telemetry            │
 │ • Dispatches to Windows Action Center        │                       │ • Returns Exit Code 0                        │
 └──────────────────────────────────────────────┘                       └──────────────────────────────────────────────┘
```

### 2.1 Component Breakdown

1. **Notification Client (`scripts/notify_host.sh`)**:
   - Accepts parameters:
     - `--title <text>`: Notification header string (defaults to "OS-Manager").
     - `--message <text>`: Main notification body.
     - `--type <info|success|warning|error|security>`: Visual categorization altering sound cues and badges.
     - `--app-id <string>`: Custom Windows application identifier for grouping.
     - `--silent`: Suppresses toast audio chime.
     - `--async` (default): Dispatches execution to a detached background subshell, returning control in under 10 milliseconds.
     - `--dry-run`: Prints the generated PowerShell command without executing it.

2. **Mandatory Non-Blocking Hook Integration**:
   - Lifecycle hooks (specifically `scripts/hooks/pre_tool_guard.sh`) MUST invoke `notify_host.sh` asynchronously using `( "${WORKSPACE_ROOT}/scripts/notify_host.sh" "$@" & ) disown` or `--async` to ensure hook execution completes in under 15 milliseconds.

3. **PowerShell WinRT Dispatcher**:
   - Generates an inline Windows Runtime (WinRT) XML template.
   - Uses `[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]`.
   - Assigns visual badges, attribution text, and audio cues mapped to the notification severity.

4. **Rate-Limiting and Debouncing Engine**:
   - Tracks event timestamps using lockfiles under `/tmp/.os_manager_notify_ratelimit_<category>`.
   - Enforces a minimum 1.0-second delay between identical notification categories to prevent desktop notification storms.

---

## 3. Event Catalog and Integration Matrix

| Triggering Component | Notification Type | Sample Title | Sample Message Content | Audio Cue |
|---|---|---|---|---|
| `scripts/hooks/pre_tool_guard.sh` | `security` | `Security Violation Blocked` | Blocked Tier 3 command: `rm -rf /` | `ms-winsoundevent:Notification.Urgent` |
| `scripts/wsl_snapshot.sh` | `success` | `Snapshot Created` | Distro exported to `D:\wsl_backup\debian_snapshot.tar` | `ms-winsoundevent:Notification.Default` |
| `scripts/clean_system.sh` | `info` | `Maintenance Complete` | Reclaimed 4.2GB across APT, UV, and PNPM caches | `ms-winsoundevent:Notification.Default` |
| `scripts/compact_host_disk.sh` | `success` | `Host Disk Compacted` | Reclaimed 12.4GB from backing `ext4.vhdx` | `ms-winsoundevent:Notification.Default` |
| `systemd/os-maintenance.service` | `error` | `Maintenance Failed` | Service exited with errors; check journal | `ms-winsoundevent:Notification.Urgent` |

---

## 4. Payload Structure and Windows Toast XML Schema

### 4.1 Native WinRT XML Schema

The dispatcher generates the following Windows 10/11 native XML payload:

```xml
<toast duration="short">
  <visual>
    <binding template="ToastGeneric">
      <text id="1">{TITLE}</text>
      <text id="2">{MESSAGE}</text>
      <text placement="attribution">OS-Manager (WSL2 Debian)</text>
    </binding>
  </visual>
  <audio src="{SOUND_EVENT}" silent="{IS_SILENT}" />
</toast>
```

### 4.2 PowerShell Invocation Template

```powershell
$xml = @"
<toast duration="short">
  <visual>
    <binding template="ToastGeneric">
      <text id="1">Security Violation Blocked</text>
      <text id="2">Blocked Tier 3 command: rm -rf /</text>
      <text placement="attribution">OS-Manager (WSL2 Debian)</text>
    </binding>
  </visual>
  <audio src="ms-winsoundevent:Notification.Urgent" />
</toast>
"@;
$doc = [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]::new();
$doc.LoadXml($xml);
$toast = [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime]::new($doc);
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]::CreateToastNotifier("OS-Manager").Show($toast);
```

---

## 5. Security Invariants and Injection Defense

### 5.1 String Sanitization and Escaping
- Double quotes, backticks, and dollar signs (`"`, `` ` ``, `$`) are strictly escaped before passing strings to PowerShell.
- Control characters and newlines are sanitized to prevent breaking the XML payload structure.

### 5.2 Process Isolation and Security Tiers
- **Tier 2 Pre-Authorization**: `scripts/notify_host.sh` is whitelisted in `scripts/hooks/pre_tool_guard.sh` and `.claude/rules/safety-tiers.md`.
- **Zero Host Mutation**: The script solely interfaces with the Windows Runtime notification manager. It writes no files to the host filesystem.

---

## 6. Resilience and Graceful Degradation

1. **Interop Disabled Detection**:
   - The script inspects `/proc/sys/fs/binfmt_misc/WSLInterop`. If disabled, it prints a terminal alert and exits cleanly with Exit Code 0.
2. **Missing `powershell.exe`**:
   - If `powershell.exe` cannot be located in `$PATH`, the script falls back to logging to `backups/logs/harness_audit.jsonl`.
3. **Background Execution Guarantee**:
   - When called from hooks, notifications execute asynchronously in detached subshells to prevent latency spikes.

---

## 7. Verification and Automated Testing Plan

### 7.1 Unit Testing (`tests/test_notify_host.sh`)
- Test argument parsing across all notification flags (`--title`, `--message`, `--type`, `--silent`, `--dry-run`).
- Test XML sanitization with special characters (`$`, `"`, `` ` ``, `<`, `>`, `&`).
- Test rate-limiting enforcement on rapid sequential invocations.
- Test graceful degradation when run with simulated missing interop.

### 7.2 Harness Integration Test Suite (`tests/test_harness.sh`)
- Assert `scripts/notify_host.sh` passes `bash -n` and `shellcheck`.
- Assert `scripts/notify_host.sh --dry-run` outputs valid PowerShell code.
- Assert `pre_tool_guard.sh` dispatches non-blocking notifications upon Tier 3 security invariant blocks.

---

## 8. Rollout Sequence and Implementation DAG

The Desktop Notification Bridge belongs to Stage 2 of the implementation plan:

1. **Stage 1 (Foundation Libraries and Tracing)**:
   - Deliverable 3.4: Hook Performance Tracing (`scripts/hooks/lib/trace_helper.sh`, `scripts/hook_benchmark.sh`).
   - Deliverable 4.1: Cross-Distribution Engine (`scripts/lib/distro.sh`, generalized package guardrails).
2. **Stage 2 (Base System Services, Notifications, and Sandbox)**:
   - Deliverable 3.1: Prometheus Metrics Exporter (`scripts/metrics_exporter.py`).
   - Deliverable 3.3: Desktop Notification Bridge (`scripts/notify_host.sh`).
   - Deliverable 3.2: Automated Host Disk Compaction (`scripts/compact_host_disk.sh`).
   - Deliverable 4.4: Agent Workspace Virtualization (`scripts/sandbox_exec.sh`).
3. **Stage 3 (Multi-Agent Mesh and Disaster Recovery)**:
   - Deliverable 4.2: Inter-Agent Message Bus (`scripts/agent_bus.py`, `scripts/bus_send.sh`).
   - Deliverable 4.3: Automated Disaster Recovery Provisioning (`scripts/bootstrap_wsl.ps1`, `scripts/post_bootstrap.sh`).
