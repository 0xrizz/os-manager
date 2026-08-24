# Specification: Full-Lifecycle Claude Code Agent Harness Architecture

> **STATUS: PARTIALLY SUPERSEDED**
> **Partially Superseded by:** `docs/superpowers/specs/2026-08-24-open-source-transformation-roadmap-design.md` on 2026-08-24.
> **Scope of Supersession:** Section 3.2 (Regex-based `PreToolUse` policy) is superseded by Shell AST analysis (`bashlex`) and ephemeral Bubblewrap (`bwrap`) rootless sandboxing. Core SSOT lifecycle hooks and symlink topology remain active baseline.

- **Date:** 2026-08-18
- **Scope:** Workspace Architecture & Agent Governance (`/home/rizz/dev/os-manager`)
- **Status:** Approved / Specification Baseline Complete
- **Target OS:** Debian GNU/Linux 13 (Trixie) on WSL2 (Kernel 6.18.x) / Windows 11 Host
- **Baseline Blueprint:** `docs/superpowers/specs/2026-08-18-os-manager-vision-mission-design.md`
- **External Literature Baseline:** Trail of Bits (`trailofbits/claude-code-config`), `edjchapman/claude-code-config`, `0xarkstar/my-claude-code-settings`, Agent Skills Open Standard (`agentskills.io`).

---

## 1. Executive Summary & Architectural Vision

This specification defines the **Full-Lifecycle Claude Code Agent Harness** for `os-manager`. The architecture implements a **Claude-First Single Source of Truth (SSOT)** model combining industry-standard community patterns (Trail of Bits defensive guardrails, edjchapman zero-copy symlink topology) with bespoke adaptations for a **Debian 13 WSL2 (ext4) vs Windows 11 Host (9P NTFS)** hybrid environment.

```text
 ══════════════════════════════════════════════════════════════════════════════════════════════════════
                                    CLAUDE-FIRST AGENT HARNESS TOPOLOGY                                  
 ══════════════════════════════════════════════════════════════════════════════════════════════════════
                                                   │
 ┌─────────────────────────────────────────────────▼──────────────────────────────────────────────────┐
 │ 1. HARNESS CONFIGURATION & GOVERNANCE LAYER                                                        │
 │    • .claude/settings.json (Permissions, Env, Hook Registrations, StatusLine)                      │
 │    • CLAUDE.md & .claude/rules/ (Deterministic Rules, Boundaries, Error Recovery Protocols)       │
 └─────────────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                                   │
        ┌──────────────────────────────────────────┼──────────────────────────────────────────┐
        ▼                                          ▼                                          ▼
 ┌──────────────┐                           ┌──────────────┐                           ┌──────────────┐
 │  LIFECYCLE   │                           │    CUSTOM    │                           │ MULTI-AGENT  │
 │    HOOKS     │                           │   COMMANDS   │                           │ INTEROP &    │
 │   ENGINE     │                           │  & SKILLS    │                           │ SUBAGENTS    │
 ├──────────────┤                           ├──────────────┤                           ├──────────────┤
 │•SessionStart │                           │• /diag       │                           │•.claude/     │
 │•PreToolUse   │                           │• /clean      │                           │  skills/     │
 │•PostToolUse  │                           │• /upgrade    │                           │•.agents/     │
 │•PostFailure  │                           │• /snapshot   │                           │  skills/     │
 │•PreCompact   │                           │• /dotfiles   │                           │•~/.gemini/   │
 │•SessionEnd   │                           │• /harness-   │                           │  config/     │
 │              │                           │  check       │                           │  skills/     │
 │              │                           │• /pair       │                           │•.claude/     │
 │              │                           │              │                           │  agents/     │
 └──────────────┘                           └──────────────┘                           └──────────────┘
```

---

## 2. External Literature Review & Naturalization Strategy

Based on comprehensive research of production-grade Claude Code community repositories:

| Repository / Source | Core Pattern Extracted | Naturalization in `os-manager` |
| :--- | :--- | :--- |
| **Trail of Bits** (`trailofbits/claude-code-config`) | Deterministic `PreToolUse` hooks exiting with code `2` to block destructive actions (`rm -rf`, force push, credentials exposure). | **Naturalized for WSL2**: Extended with the **4-Tier Safety Matrix**, canonical path resolution (`realpath -m`) to protect Windows Host directories (`/mnt/c/Windows`, `AppData`), and fail-closed security. |
| **edjchapman** (`edjchapman/claude-code-config`) | Single Source of Truth (SSOT) symlink propagation, composable permission templates, automated formatting on edit (`PostToolUse`). | **Naturalized for Multi-Agent**: Established `.claude/skills/` as master, auto-propagated to `.agents/skills/` (Universal Agent standard) and `~/.gemini/config/skills/` (Google Antigravity `agy`). |
| **0xarkstar & JNK234** (`my-claude-code-settings`, `dotclaude`) | Multi-tier review subagents, dedicated `.claude/rules/` directory for modular prompt invariants, audio/terminal completion feedback. | **Naturalized for OS Governance**: Created dedicated subagents (`security-auditor`, `system-operator`) and rulesets for ext4 vs 9P I/O discipline and Superpowers gating. |
| **Agent Skills Open Spec** (`agentskills.io`) | Standardized directory bundles (`skills/<name>/SKILL.md` + `references/`), parameter declarations (`argument-hint`, `arguments`). | **Naturalized for CLI & Agent Pairing**: Unified slash commands and skills under the modern directory bundle schema. |

---

## 3. Core Design Principles

1. **Deterministic Defense-in-Depth vs. Probabilistic Models**:
   - Security policies and filesystem invariants never rely on LLM goodwill. Hard rules are enforced deterministically via Unix exit codes (`Exit 2` for clean blocking intervention).
2. **Claude-First Single Source of Truth (SSOT)**:
   - All skill definitions, prompt protocols, and tool configs originate under `.claude/`. Downstream consumers (`.agents/skills/`, Antigravity `~/.gemini/config/skills/`) consume these assets via deterministic, zero-copy relative symlinks.
3. **Fail-Closed Security & Clean Feedback Loop**:
   - If a guardrail script fails to parse input or detects a critical ambiguity, it fails closed (`Exit 2`), feeding actionable diagnostic remediation to `stderr` so the model can self-correct without crashing.
4. **Closed-Loop Auto-Healing Quality Gate**:
   - Every file edit or write (`Edit`/`Write`) is immediately validated by formatters and linters (`shfmt`, `bash -n`, `shellcheck`, `jq`, `py_compile`). Linter failures trigger an instant repair turn for the agent.
5. **WSL2 Ext4 vs. Windows 9P Mount Boundary Isolation**:
   - Heavy I/O, repositories, virtualenvs, and runtime assets reside exclusively on native ext4 (`/home/rizz/`). NTFS 9P mounts (`/mnt/c/`, `/mnt/d/`) are strictly restricted to backup targets and read-only host inspections.

---

## 4. Component Specifications

### Component 1: Lifecycle Hooks Engine

The hook engine intercepts agent lifecycle transitions and tool executions. All hook paths leverage `${CLAUDE_PROJECT_DIR}` variable interpolation for absolute portability.

```text
                  ┌────────────────────────────────────────┐
                  │       Agent Triggers Lifecycle Event   │
                  └───────────────────┬────────────────────┘
                                      │
           ┌──────────────────────────┼──────────────────────────┐
           ▼                          ▼                          ▼
     Exit Code 0                Exit Code 2                Exit Code 1
  ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────────┐
  │  ALLOW / PASS    │       │ BLOCK / REMEDIATE│       │ FAIL-OPEN WARNING    │
  │  Execution       │       │ Intercept tool,  │       │ Log warning,         │
  │  proceeds        │       │ feed stderr to   │       │ execution continues  │
  │  normally        │       │ LLM context      │       │                      │
  └──────────────────┘       └──────────────────┘       └──────────────────────┘
```

#### A. Hook Event Specifications

| Hook Event | Matcher | Handler Script | Timeout | Objective & Behavioral Semantics |
| :--- | :--- | :--- | :--- | :--- |
| **`SessionStart`** | `*` | `scripts/hooks/session_preflight.sh` | 10s | Inspects WSL2 RAM headroom (>500MB), Swap presence, binary paths (`node`, `uv`, `agy`, `shellcheck`, `shfmt`), validates symlink bridges, and initializes `backups/logs/harness_audit.jsonl`. |
| **`PreToolUse`** | `Bash\|Edit\|Write` | `scripts/hooks/pre_tool_guard.sh` | 15s | **Deterministic 4-Tier Guardrail Engine**. Parses `stdin` JSON, canonicalizes target paths (`realpath -m`), normalizes shell flags, and enforces strict boundary blocks (`Exit 2`). |
| **`PostToolUse`** | `Edit\|Write` | `scripts/hooks/post_tool_lint.sh` | 30s | **Auto-Healing Validation Engine**. Formats and lints modified files (`shfmt`, `bash -n`, `shellcheck`, `jq`, `py_compile`). On defect, returns `Exit 2` with line-level diagnostic feedback. |
| **`PostToolUseFailure`**| `*` | `scripts/hooks/post_tool_failure.sh` | 10s | Captures execution errors and logs structured telemetry to `backups/logs/harness_errors.jsonl`. |
| **`PreCompact`** | `*` | `scripts/hooks/pre_compact_state.sh` | 10s | Snapshots git status, dirty files, and active task state to `backups/logs/compact_snapshot.json` before context window truncation. |
| **`SessionEnd`** | `*` | `scripts/hooks/session_cleanup.sh` | 10s | Flushes audit logs, cleans ephemeral session state, and ensures no orphan subshells remain. |

#### B. The 4-Tier PreToolUse Safety Matrix

1. **Tier 0 (Autonomous / Read-Only)** $\rightarrow$ **`ALLOW (Exit 0)`**:
   - `ls`, `cat`, `grep`, `find`, `git status`, `git diff`, `uname`, `free`, `df`, `systemctl status`, `ps`, `top -bn1`.
2. **Tier 1 (Workspace Contained)** $\rightarrow$ **`ALLOW (Exit 0)`**:
   - File reads, writes, edits, and script invocations strictly bounded inside canonical workspace `/home/rizz/dev/os-manager/`.
3. **Tier 2 (Controlled System Operations)** $\rightarrow$ **`ALLOW (Exit 0)`**:
   - Whitelisted maintenance scripts: `./scripts/clean_system.sh`, `./scripts/sys_diag.sh`, `./scripts/update_runtimes.sh`, `./scripts/wsl_snapshot.sh`, `sudo apt update`, `pnpm store prune`, `uv cache clean`.
4. **Tier 3 (Strict Invariant Violations)** $\rightarrow$ **`BLOCK (Exit 2)`**:
   - **Root / Home Obliteration**: `rm -rf /`, `rm -rf /*`, `rm -rf ~`, `rm -rf $HOME`, `rm -rf /home/rizz`.
   - **Host & WSL Lifecycle Sabotage**: `wsl --unregister`, `wsl.exe --unregister`, `wsl --shutdown`, `wsl.exe --shutdown`.
   - **Indiscriminate Package Purging**: `apt-get purge *`, `apt remove -y *`, `dpkg --purge *`.
   - **Direct Raw Disk Manipulation**: `mkfs.*`, `fdisk`, `dd if=.* of=/dev/sd.*`.
   - **Windows NTFS Host Intrusion**: Modifying `/mnt/c/Windows/**`, `/mnt/c/Program Files/**`, `/mnt/c/Users/*/AppData/**`.
   - **Linux Core System Destruction**: Modifying `/etc/passwd`, `/etc/shadow`, `/boot/**`, `/dev/**`.

---

### Component 2: Custom Slash Commands & Unified Skills (`.claude/skills/` & `.claude/commands/`)

Custom slash commands provide ergonomic, deterministic shortcuts that encapsulate multi-step operational runbooks with parameter validation.

```text
.claude/
├── commands/
│   ├── diag.md            # /diag: Pillar 1 System Diagnostics
│   ├── clean.md           # /clean: Pillar 1 Safe Storage & Cache Pruning
│   ├── upgrade.md         # /upgrade: Pillar 3 Coordinated Runtimes Update
│   ├── snapshot.md        # /snapshot: Pillar 4 WSL Point-in-Time Snapshot
│   ├── dotfiles.md        # /dotfiles: Pillar 4 State Backup & Diff Sync
│   ├── harness-check.md   # /harness-check: Harness Self-Test & Diagnostic Matrix
│   └── pair.md            # /pair: Pillar 2 Tmux Multi-Agent Session Orchestrator
└── skills/
    ├── sys-diag/SKILL.md
    ├── clean-system/SKILL.md
    ├── update-runtimes/SKILL.md
    ├── wsl-snapshot/SKILL.md
    ├── tmux-agents/SKILL.md
    └── ... (Superpowers Suite)
```

#### Command Specifications

1. **`/diag`** (`.claude/commands/diag.md`):
   - **Invokes**: `./scripts/sys_diag.sh $ARGUMENTS`
   - **Flags**: `--full` (includes 9P I/O latency & network sockets), `--json` (machine output).
   - **Behavior**: Evaluates kernel state, RAM/Swap pressure, root ext4 capacity, and failed systemd units.
2. **`/clean`** (`.claude/commands/clean.md`):
   - **Invokes**: `./scripts/clean_system.sh $ARGUMENTS`
   - **Flags**: `--dry-run` (estimate reclaimable bytes), `--all` (includes build cache eviction).
   - **Behavior**: Displays before/after disk space delta (`df -h /`).
3. **`/upgrade`** (`.claude/commands/upgrade.md`):
   - **Invokes**: `./scripts/update_runtimes.sh $ARGUMENTS`
   - **Flags**: `--check` (dry run version diff), `--system-only`, `--runtimes-only`, `--ai-only`.
   - **Behavior**: Verifies binary versions in `$PATH` across Debian packages, PNPM, Bun, UV, and AI CLIs.
4. **`/snapshot`** (`.claude/commands/snapshot.md`):
   - **Invokes**: `./scripts/wsl_snapshot.sh $ARGUMENTS`
   - **Flags**: `--verify` (sha256 checksum check), `--prune` (keep last 3 snapshots).
   - **Behavior**: Generates compressed timestamped tarball to `/mnt/d/wsl_backup`.
5. **`/dotfiles`** (`.claude/commands/dotfiles.md`):
   - **Invokes**: `./scripts/dotfiles_sync.sh $ARGUMENTS`
   - **Subcommands**: `backup`, `diff`, `restore <tag>`.
   - **Behavior**: Performs non-destructive visual diffs before applying dotfile changes.
6. **`/harness-check`** (`.claude/commands/harness-check.md`):
   - **Invokes**: `./scripts/harness_check.sh`
   - **Behavior**: Executes synthetic guardrail probes (mock `rm -rf /`, Windows path access), validates linter binary availability, tests symlink integrity, and reports a Pass/Fail scorecard.
7. **`/pair`** (`.claude/commands/pair.md`):
   - **Invokes**: `./scripts/tmux_agents.sh $ARGUMENTS`
   - **Subcommands**: `start` (spawns 3-pane layout: Claude Code + Antigravity `agy` + System Monitor), `attach`, `status`, `kill`.

---

### Component 3: Multi-Agent Interoperability, Skills & Custom Subagents

The architecture establishes `.claude/skills/` as the immutable master registry, bridged to external agent ecosystems and augmented with specialized subagents.

```text
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                      MASTER SKILL REGISTRY: .claude/skills/                            │
 │  ├── sys-diag/SKILL.md             ├── brainstorming/SKILL.md                          │
 │  ├── clean-system/SKILL.md         ├── writing-plans/SKILL.md                          │
 │  ├── update-runtimes/SKILL.md      ├── executing-plans/SKILL.md                        │
 │  ├── wsl-snapshot/SKILL.md         ├── test-driven-development/SKILL.md                │
 │  └── tmux-agents/SKILL.md          └── ... (Superpowers Suite)                         │
 └───────────────────────────────────────────┬────────────────────────────────────────────┘
                                             │
                         [scripts/sync_agent_skills.sh]
                                             │
             ┌───────────────────────────────┴───────────────────────────────┐
             ▼ (Relative Symlink)                                            ▼ (Global Path Symlink)
 ┌───────────────────────────────────────┐                       ┌───────────────────────────────────────┐
 │   Universal Agent Standard Bridge     │                       │       Google Antigravity Bridge       │
 │   Directory: .agents/skills/          │                       │   Directory: ~/.gemini/config/skills/ │
 │   • Relative: ../../.claude/skills/*  │                       │   • Absolute: /home/rizz/.../.claude/*│
 └───────────────────────────────────────┘                       └───────────────────────────────────────┘
```

#### A. Custom Subagents Registry (`.claude/agents/*.md`)
Specialized subagents are defined declaratively with strict tool boundaries:
1. **`security-auditor`** (`.claude/agents/security-auditor.md`):
   - **Tools**: `Read`, `Grep`, `Glob`, `Bash(git *)`, `Bash(shellcheck *)`
   - **Disallowed Tools**: `Edit`, `Write`, `Workflow`
   - **Model & Effort**: `sonnet`, `high`
   - **Role**: Read-only vulnerability, secret leak, and permission analysis.
2. **`system-operator`** (`.claude/agents/system-operator.md`):
   - **Tools**: `Bash`, `Read`, `Grep`, `Glob`, `Edit`, `Write`
   - **Isolation**: `worktree`
   - **Model & Effort**: `inherit`, `high`
   - **Role**: Safe script refactoring and system automation execution within git worktrees.

#### B. Skill Synchronization Protocol: `scripts/sync_agent_skills.sh`
1. Cleans dead/broken symlinks in `.agents/skills/` and `~/.gemini/config/skills/`.
2. Creates deterministic relative symlinks for `.agents/skills/<name>`.
3. Creates absolute symlinks for `~/.gemini/config/skills/<name>`.
4. Executes automatically during `SessionStart` preflight.

---

### Component 4: Hierarchical Rules & Superpowers Enforcement

The hierarchy guarantees that security invariants and engineering disciplines cannot be overridden by user prompts.

```text
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ Layer 1: Deterministic Lifecycle Hooks (.claude/settings.json & scripts/hooks/)         │
│ • Exit Code 2 hard blocks (Tier 3 violations, Windows 9P protection, syntax failures)   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ Layer 2: Modular Rulesets & Invariants (.claude/rules/*.md & CLAUDE.md)                 │
│ • wsl-boundaries.md (ext4 vs 9P storage rules, I/O performance limits)                  │
│ • safety-tiers.md (Autonomous vs Gated action classifications)                          │
│ • error-recovery.md (Recovery & auto-repair protocol)                                   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ Layer 3: Superpowers Methodology Suite (.claude/skills/)                                │
│ • Brainstorming Hard-Gates, TDD discipline, Evidence-first completion                   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ Layer 4: Turn-Level Prompt Instructions                                                 │
│ • Strictly bounded by all higher layers                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

#### A. Modular Rules Directory (`.claude/rules/*.md`)
Following community best practices (from Trail of Bits and `my-claude-code-settings`), prompt invariants are split into modular rule files:
1. `.claude/rules/wsl-boundaries.md`: Strict rules governing native ext4 vs 9P mounts, preventing heavy package builds on Windows drives.
2. `.claude/rules/safety-tiers.md`: Explicit boundaries between autonomous read-only/cleanup commands and gated confirmation actions.
3. `.claude/rules/error-recovery.md`: Self-healing feedback loops when tools fail or hooks intervene.

---

## 5. Master Configuration Schema (`.claude/settings.json`)

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

---

## 6. Implementation Roadmap & Deliverables

1. **Phase 1: Lifecycle Hook Scripts (`scripts/hooks/`)**:
   - `scripts/hooks/session_preflight.sh`
   - `scripts/hooks/pre_tool_guard.sh`
   - `scripts/hooks/post_tool_lint.sh`
   - `scripts/hooks/post_tool_failure.sh`
   - `scripts/hooks/pre_compact_state.sh`
   - `scripts/hooks/session_cleanup.sh`
2. **Phase 2: Master Harness Configuration**:
   - Configure `.claude/settings.json` with permissions, environment, and hook definitions.
3. **Phase 3: Custom Slash Commands Palette (`.claude/commands/`)**:
   - `.claude/commands/diag.md`
   - `.claude/commands/clean.md`
   - `.claude/commands/upgrade.md`
   - `.claude/commands/snapshot.md`
   - `.claude/commands/dotfiles.md`
   - `.claude/commands/harness-check.md`
   - `.claude/commands/pair.md`
4. **Phase 4: Custom Subagents Registry (`.claude/agents/`)**:
   - `.claude/agents/security-auditor.md`
   - `.claude/agents/system-operator.md`
5. **Phase 5: Modular Rules Invariants (`.claude/rules/`)**:
   - `.claude/rules/wsl-boundaries.md`
   - `.claude/rules/safety-tiers.md`
   - `.claude/rules/error-recovery.md`
6. **Phase 6: Multi-Agent Bridge & Self-Test Suite**:
   - `scripts/sync_agent_skills.sh`
   - `scripts/harness_check.sh`
   - Initial sync to `.agents/skills/` and `~/.gemini/config/skills/`.
7. **Phase 7: Governance Integration & CLAUDE.md Update**:
   - Update `CLAUDE.md` to seal operational invariants and Superpowers workflow rules.
