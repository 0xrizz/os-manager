# UX and DX Enhancements Design Specification

## Problem Statement

Security tools and governance guardrails frequently frustrate engineers when hard execution blocks halt workflow progress. The current `os-manager` harness blocks Tier 3 commands using an unconditional non-zero exit status, requiring manual intervention even when a command poses no threat to host integrity. Additionally, new users require manual configuration of settings and hooks, creating setup friction. Terminal outputs also lack a unified visual standard, reducing status scannability during long coding sessions.

## Architecture and Core Systems

This specification defines three interconnected Developer Experience (DX) subsystems:

1. **Auto-Sandbox Fallback Engine**: Reroutes broad or risky shell commands from `scripts/hooks/pre_tool_guard.sh` into disposable Podman containers instead of aborting execution.
2. **Zero-Touch Onboarding Installer (`install.sh`)**: Provides an idempotent, single-command setup pipeline that configures permissions, hooks, and dependencies across Linux, WSL2, and macOS.
3. **Terminal Ergonomics and Micro-Badge Standard**: Implements standardized single-line status badges and compact Unicode dashboard cards across all CLI tools and slash commands.

```text
 ══════════════════════════════════════════════════════════════════════════════════════════════════════
                                    UX & DX ENHANCEMENT ARCHITECTURE                                   
 ══════════════════════════════════════════════════════════════════════════════════════════════════════
                                                 │
 ┌───────────────────────────────────────────────▼──────────────────────────────────────────────────┐
 │ USER / AGENT EXECUTION LAYER (CLI, Hooks, Slash Commands)                                        │
 └───────────────────────────────────────┬──────────────────────────────────────────────────────────┘
                                         │
         ┌───────────────────────────────┼───────────────────────────────┐
         ▼                               ▼                               ▼
 ┌──────────────────────────────┐┌──────────────────────────────┐┌──────────────────────────────┐
 │ AUTO-SANDBOX FALLBACK        ││ ZERO-TOUCH ONBOARDING        ││ TERMINAL ERGONOMICS          │
 │ (pre_tool_guard.sh)          ││ (install.sh)                 ││ (Micro-Badges & Dashboard)   │
 ├──────────────────────────────┤├──────────────────────────────┤├──────────────────────────────┤
 │• Hard Veto: Host Sabotage    ││• Platform Probe (distro.sh)  ││• [OK], [WARN], [SANDBOX]     │
 │• Auto-Sandbox: Risky Ops     ││• Idempotent settings.json    ││• Compact ASCII Cards         │
 │• sandbox_exec.sh Isolation   ││• Symlink Bridge Activation   ││• Proactive Context Hints     │
 └──────────────────────────────┘└──────────────────────────────┘└──────────────────────────────┘
```

---

## 1. Auto-Sandbox Fallback Engine

### Command Classification Matrix

The `scripts/hooks/pre_tool_guard.sh` hook classifies tool invocations into three deterministic execution tiers:

| Action Category | Target / Pattern | Policy | Result |
| :--- | :--- | :--- | :--- |
| **Host Sabotage** | `/mnt/c/Windows/**`, `/etc/shadow`, `/boot/**`, `wsl --unregister` | Hard Veto | Exit Code 2 with diagnostic error message |
| **Risky Shell Operations** | `rm -rf <path>`, `apt purge *`, untrusted clone/build scripts | Auto-Sandbox | Rewrite command to `scripts/sandbox_exec.sh` with Exit Code 0 |
| **Standard Operations** | Reads, edits within workspace, safe diagnostics | Allowed | Normal execution with Exit Code 0 |

### Interception and Rewriting Flow

When `pre_tool_guard.sh` detects a risky command:

1. The hook preserves the original command arguments.
2. The hook verifies that the Podman container runtime is available on the host.
3. If Podman is operational, the hook executes the command through `scripts/sandbox_exec.sh --workdir "$PWD" -- <original_cmd>`.
4. The hook prepends standard output with the marker `[SANDBOXED EXECUTION]`.
5. The hook returns Exit Code 0 to preserve the interactive agent loop without workflow interruption.
6. If Podman is absent, the hook falls back to a standard Exit Code 2 with an explicit instruction to install Podman or run in a confined directory.

---

## 2. Zero-Touch Onboarding Installer (`install.sh`)

### Automated Setup Workflow

The root installer script `install.sh` handles end-to-end environment bootstrapping:

```text
[curl -fsSL .../install.sh | bash]
                 │
                 ▼
      [Detect OS & Platform]  ──► Uses scripts/lib/distro.sh
                 │
                 ▼
      [Validate Dependencies] ──► Checks jq, python3, podman, git
                 │
                 ▼
      [Configure Settings]    ──► Idempotently merges hooks into .claude/settings.json
                 │
                 ▼
      [Sync Multi-Agent SSOT] ──► Runs scripts/sync_agent_skills.sh
                 │
                 ▼
      [Execute Self-Check]    ──► Runs smoke tests on security hooks
                 │
                 ▼
      [Display Status Card]   ──► Renders 3-line quickstart summary card
```

### Invariants and Safety Guarantees

* **Idempotency**: Running `install.sh` multiple times produces identical state without duplicating configuration keys.
* **JSON Integrity**: Configuration injection uses `jq` filters rather than string concatenation, preventing syntax corruption in `.claude/settings.json`.
* **Zero Host Contamination**: Installation operates strictly within `${HOME}` and the local repository directory.

---

## 3. Terminal Ergonomics and Proactive Slash Commands

### Micro-Badge Specification

CLI utilities format operational output using uniform ANSI color badges:

* `[OK]` (`\033[32m`): Successful operation with zero defects.
* `[WARN]` (`\033[33m`): Non-fatal threshold warning (such as disk slack exceeding 10GB or memory headroom falling below 500MB).
* `[SANDBOX]` (`\033[36m`): Isolated execution inside a disposable container.
* `[BLOCK]` (`\033[31m`): Security invariant violation blocked deterministically.

### ASCII Status Dashboard

The `/diag` command and `scripts/sys_diag.sh` utility default to an 8-line compact Unicode status card:

```text
┌─ os-manager v1.2 ────────────────────────────────────────────────────────┐
│  Host: Debian 13 (WSL2)  •  Kernel: 6.18.33  •  RAM: 3.2G / 16G (20%)    │
│  Harness: 6 Hooks Active  •  Security: Tier 0-3 Guard  •  Sandbox: Ready  │
│  Storage: 42G / 256G (16%) • Disk Slack: 4.1GB • Metrics: 127.0.0.1:9100 │
└──────────────────────────────────────────────────────────────────────────┘
```

The `--json` flag preserves complete machine-readable diagnostics for automated pipelines.

### Proactive Hook Hints

Lifecycle hooks inject actionable slash command suggestions into context upon detecting specific system states:

* **Session Initialization (`scripts/hooks/session_preflight.sh`)**: When package cache size exceeds 2GB, the preflight hook emits `Hint: Package cache size is 2.4GB. Run /clean to reclaim space.`
* **Failure Recovery (`scripts/hooks/post_tool_failure.sh`)**: When syntax validation fails on file modification, the hook emits `Hint: Syntax error in target file. Auto-healing protocol active.`

---

## 4. Verification and Test Plan

### Test Suite Structure

A dedicated test suite `tests/test_ux_dx.sh` verifies all enhancements:

1. **Auto-Sandbox Interception Tests**:
   - Verify that destructive root operations (`rm -rf /`) remain blocked by hard veto.
   - Verify that broad project deletions execute inside Podman without deleting host files outside the container.
   - Verify that output streams include the `[SANDBOXED EXECUTION]` header.
2. **Installer Integration Tests**:
   - Run `install.sh --dry-run` to verify platform detection and dependency validation.
   - Verify that `.claude/settings.json` receives all 6 lifecycle hook registrations.
   - Test idempotency by executing the installer twice against a temporary configuration directory.
3. **Ergonomics and Badge Tests**:
   - Verify that `/diag` produces standard ANSI micro-badges.
   - Verify that `--json` returns valid JSON matching the system schema.
   - Verify that proactive context hints trigger only when threshold conditions are met.

---

## 5. Implementation Roadmap

1. **Phase 1**: Update `scripts/hooks/pre_tool_guard.sh` to implement auto-sandbox fallback for risky shell operations.
2. **Phase 2**: Author `install.sh` root installer with idempotent configuration merging and platform detection.
3. **Phase 3**: Refactor `scripts/sys_diag.sh` and `/diag` command to output standardized micro-badges and the compact dashboard card.
4. **Phase 4**: Add `tests/test_ux_dx.sh` and integrate into the master test harness `tests/test_harness.sh`.
