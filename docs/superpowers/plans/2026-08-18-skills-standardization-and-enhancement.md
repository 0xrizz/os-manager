# Skills Standardization & Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standardize and enhance all operational skills in `.claude/skills/` to achieve 100% compliance with Agent Skills specifications (agentskills.io), Skill Discovery Optimization (SDO), and The Elements of Agent Style.

**Architecture:** Add standard YAML frontmatter with third-person "Use when..." triggering symptoms to existing stub skills (`sys-diag`, `clean-system`, `update-runtimes`, `wsl-snapshot`, `tmux-agents`). Create missing core pillar skills (`dotfiles`, `harness-check`) to complete the Single Source of Truth (SSOT). Expand test suite assertions in `tests/test_harness.sh` to automatically validate skill frontmatter syntax and verify 21-skill zero-copy symlink propagation across Universal Agent and Google Antigravity.

**Tech Stack:** Markdown, YAML Frontmatter, Bash, ShellCheck, Agent-Style CLI (`agent-style review`).

**Spec:** Audited findings from `docs/superpowers/specs/2026-08-18-os-manager-vision-mission-design.md` and `.claude/skills/writing-skills/SKILL.md`.

## Global Constraints

- Every skill `SKILL.md` MUST include YAML frontmatter with `name` (letters, numbers, hyphens only) and `description` (starts with "Use when...", third-person, symptoms-focused, no workflow summary, <500 characters).
- All prose and documentation MUST adhere to *The Elements of Agent Style* (active voice, concise, direct directives, 0 violations on `agent-style review`).
- File paths and script invocations MUST use canonical absolute workspace paths (`/home/rizz/dev/os-manager/scripts/...`) or relative repo structures.
- All modified and newly created skills MUST be synchronized across `.agents/skills/` and `~/.gemini/config/skills/` via `scripts/sync_agent_skills.sh`.
- All automated unit test assertions in `tests/test_harness.sh` and `./scripts/harness_check.sh` MUST pass with 0 failures.

---

### Task 1: Standardize `sys-diag` & `clean-system` Skills

**Files:**
- Modify: `.claude/skills/sys-diag/SKILL.md`
- Modify: `.claude/skills/clean-system/SKILL.md`

**Interfaces:**
- Consumes: `./scripts/sys_diag.sh`, `./scripts/clean_system.sh`, `.claude/commands/diag.md`, `.claude/commands/clean.md`
- Produces: SDO-discoverable skills for system diagnostics and disk cleanup

- [ ] **Step 1: Update `.claude/skills/sys-diag/SKILL.md`**

Replace content with standardized YAML frontmatter, SDO trigger description, CLI options table (`--full`, `--json`), safety classification (Tier 0 Read-Only), and output interpretation guide.

```markdown
---
name: sys-diag
description: Use when diagnosing system health issues, checking RAM/swap pressure, inspecting storage utilization, verifying systemd service failures, or analyzing WSL2 kernel metrics
---

# System Diagnostics Skill

Comprehensive diagnostic engine for inspecting Debian WSL2 system health, resource headroom, running processes, and active systemd units.

## Trigger Scenarios
- High memory pressure or sluggish terminal response
- Investigating systemd unit degradation or crashed services
- Verifying WSL2 kernel, uptime, or network connectivity
- Periodic or pre-maintenance health baseline inspection

## Invocation
```bash
/home/rizz/dev/os-manager/scripts/sys_diag.sh [flags]
```

## Command Options
| Option | Description |
| :--- | :--- |
| *(none)* | Standard diagnostic output (kernel, memory, ext4 disk, top CPU/RAM processes, failed systemd units) |
| `--full` | Extended diagnostics including network listening sockets and 9P mount inspection |
| `--json` | Machine-readable JSON output for automated telemetry and tooling |

## Safety Classification
- **Tier 0 (Autonomous Read-Only)**: Non-destructive execution with zero side effects.
```

- [ ] **Step 2: Update `.claude/skills/clean-system/SKILL.md`**

Replace content with standardized YAML frontmatter, SDO trigger description, CLI options table (`--dry-run`, `--all`), safety classification (Tier 2 Controlled Operation), and reclaim verification steps.

```markdown
---
name: clean-system
description: Use when ext4 disk space is low, package caches are bloated, or after intensive development builds requiring APT, UV, PNPM, Bun, and /tmp cache eviction
---

# Safe System Cleanup Skill

Reclaims disk space on the native ext4 WSL root volume by safely removing package caches, unreferenced dependencies, runtime cache stores, and temporary files.

## Trigger Scenarios
- Root volume (`/`) storage exceeding warning thresholds (>80% utilization)
- Bloated APT archive caches following system updates
- Accumulated Python UV package caches or orphaned virtual environments
- Stale PNPM store items, Bun install caches, or lingering `/tmp` artifacts

## Invocation
```bash
/home/rizz/dev/os-manager/scripts/clean_system.sh [flags]
```

## Command Options
| Option | Description |
| :--- | :--- |
| *(none)* | Standard safe cleanup (APT cache/autoremove, UV cache, PNPM/Bun cache, `/tmp` files) |
| `--dry-run` | Inspects and estimates reclaimable disk space without deleting files |
| `--all` | Includes aggressive compiler and build cache eviction |

## Safety Classification
- **Tier 2 (Controlled System Operation)**: Authorized cleanup script preserving configuration files and active repositories.
```

- [ ] **Step 3: Run style audit on modified skills**

Run: `agent-style review --audit-only .claude/skills/sys-diag/SKILL.md .claude/skills/clean-system/SKILL.md`
Expected: 0 violations for both files.

- [ ] **Step 4: Commit Task 1 changes**

```bash
git add .claude/skills/sys-diag/SKILL.md .claude/skills/clean-system/SKILL.md
git commit -m "docs(skills): standardize sys-diag and clean-system with SDO frontmatter"
```

---

### Task 2: Standardize `update-runtimes`, `wsl-snapshot`, & `tmux-agents` Skills

**Files:**
- Modify: `.claude/skills/update-runtimes/SKILL.md`
- Modify: `.claude/skills/wsl-snapshot/SKILL.md`
- Modify: `.claude/skills/tmux-agents/SKILL.md`

**Interfaces:**
- Consumes: `./scripts/update_runtimes.sh`, `./scripts/wsl_snapshot.sh`, `./scripts/tmux_agents.sh`
- Produces: SDO-discoverable skills for toolchain upgrades, snapshots, and tmux pairing

- [ ] **Step 1: Update `.claude/skills/update-runtimes/SKILL.md`**

Add YAML frontmatter, SDO trigger description, package manager breakdown (APT, NVM/Node, PNPM, Bun, UV, Cloudflare Wrangler, AI CLIs), `--check` flag documentation, and failure recovery.

```markdown
---
name: update-runtimes
description: Use when updating system packages, upgrading developer runtimes (Node.js, PNPM, Bun, Python UV), or refreshing global AI CLIs (@anthropic-ai/claude-code, agy, wrangler)
---

# Update Runtimes Skill

Coordinates rolling updates across Debian package repositories, Node.js runtime toolchains, Python package managers, and global AI engineering tools.

## Trigger Scenarios
- Scheduled weekly or monthly developer toolchain refreshes
- Upgrading Claude Code CLI or Google Antigravity (`agy`) to latest releases
- Syncing Debian security patches via `apt update`
- Updating global NPM, Bun, or Python UV tool binaries

## Invocation
```bash
/home/rizz/dev/os-manager/scripts/update_runtimes.sh [flags]
```

## Command Options
| Option | Description |
| :--- | :--- |
| *(none)* | Executes coordinated updates across APT, NVM/Node, PNPM, Bun, UV, and global CLIs |
| `--check` | Checks for available package updates without applying changes |

## Safety Classification
- **Tier 2 (Controlled System Operation)**: Standard runtime updates preserving environment configuration.
```

- [ ] **Step 2: Update `.claude/skills/wsl-snapshot/SKILL.md`**

Add YAML frontmatter, SDO trigger description, target directory specification (`/mnt/d/wsl_backup`), flags (`--verify`, `--prune`), SHA256 checksumming, and recovery instructions.

```markdown
---
name: wsl-snapshot
description: Use when creating full disaster recovery tarball snapshots of the Debian WSL instance, verifying backup checksums, or archiving state before major OS upgrades
---

# WSL Disaster Recovery Snapshot Skill

Generates compressed point-in-time tarball archives of the native ext4 Debian WSL2 environment to dedicated external Windows backup storage (`/mnt/d/wsl_backup`).

## Trigger Scenarios
- Pre-upgrade disaster recovery checkpoints before distribution upgrades
- Scheduled weekly or monthly offsite snapshot archival
- Verification of backup integrity using SHA256 checksums
- Pruning obsolete archive tarballs to preserve disk space

## Invocation
```bash
/home/rizz/dev/os-manager/scripts/wsl_snapshot.sh [flags]
```

## Command Options
| Option | Description |
| :--- | :--- |
| *(none)* | Creates a compressed snapshot (`.tar.gz`) in `/mnt/d/wsl_backup/` with SHA256 checksum |
| `--verify` | Verifies SHA256 checksum of existing backup archives |
| `--prune` | Retains the 3 most recent backups and purges older archives |

## Safety Classification
- **Tier 2 (Controlled System Operation)**: Authorized backup procedure restricted to external mount `/mnt/d/wsl_backup`.
```

- [ ] **Step 3: Update `.claude/skills/tmux-agents/SKILL.md`**

Add YAML frontmatter, SDO trigger description, 3-pane layout breakdown (Claude Code, Google Antigravity `agy`, monitoring pane), subcommands (`start`, `attach`), and session management.

```markdown
---
name: tmux-agents
description: Use when launching or attaching to a paired multi-agent engineering workspace running Claude Code, Google Antigravity (agy), and live system diagnostics in Tmux
---

# Multi-Agent Tmux Pairing Skill

Orchestrates a coordinated 3-pane Tmux session designed for paired engineering between Claude Code and Google Antigravity (`agy`), accompanied by live resource monitoring.

## Trigger Scenarios
- Starting a collaborative multi-agent development session
- Reattaching to an existing detached agent pairing session
- Running live background system telemetry alongside AI agent workflows

## Invocation
```bash
/home/rizz/dev/os-manager/scripts/tmux_agents.sh [subcommand]
```

## Workspace Architecture
```text
┌──────────────────────────────┬──────────────────────────────┐
│                              │                              │
│         Claude Code          │      Google Antigravity      │
│        (Primary Agent)       │         (`agy` CLI)          │
│                              │                              │
├──────────────────────────────┴──────────────────────────────┤
│                   System Telemetry & Logs                   │
└─────────────────────────────────────────────────────────────┘
```

## Subcommands
| Subcommand | Description |
| :--- | :--- |
| `start` | Initializes a new 3-pane paired workspace session |
| `attach` | Reattaches to an active background pairing session |

## Safety Classification
- **Tier 2 (Controlled System Operation)**: Workspace process and terminal multiplexer manager.
```

- [ ] **Step 4: Run style audit on modified skills**

Run: `agent-style review --audit-only .claude/skills/update-runtimes/SKILL.md .claude/skills/wsl-snapshot/SKILL.md .claude/skills/tmux-agents/SKILL.md`
Expected: 0 violations across all 3 files.

- [ ] **Step 5: Commit Task 2 changes**

```bash
git add .claude/skills/update-runtimes/SKILL.md .claude/skills/wsl-snapshot/SKILL.md .claude/skills/tmux-agents/SKILL.md
git commit -m "docs(skills): standardize update-runtimes, wsl-snapshot, and tmux-agents"
```

---

### Task 3: Create Missing `dotfiles` Skill

**Files:**
- Create: `.claude/skills/dotfiles/SKILL.md`

**Interfaces:**
- Consumes: `./scripts/dotfiles_sync.sh`, `.claude/commands/dotfiles.md`
- Produces: Complete SSOT skill for dotfile backup, diffing, and restoration

- [ ] **Step 1: Write `.claude/skills/dotfiles/SKILL.md`**

Author the skill with YAML frontmatter, SDO trigger description, subcommands (`backup`, `diff`, `restore`), target configuration files (`~/.bashrc`, `~/.tmux.conf`, `~/.gitconfig`), backup storage location (`backups/dotfiles/`), and explicit confirmation gate rules.

```markdown
---
name: dotfiles
description: Use when backing up user configuration files (~/.bashrc, ~/.tmux.conf, ~/.gitconfig), inspecting diffs against backups, or safely restoring configurations
---

# Dotfiles Synchronization & State Protection Skill

Manages backup, diff inspection, and safe restoration of user dotfiles between active user home directory and the repository backup store (`backups/dotfiles/`).

## Trigger Scenarios
- Backing up dotfiles before making experimental shell or tmux configuration edits
- Inspecting configuration drift between active `$HOME` dotfiles and repo backups
- Restoring verified baseline configurations after environment resets

## Invocation
```bash
/home/rizz/dev/os-manager/scripts/dotfiles_sync.sh <subcommand>
```

## Tracked Files
- `~/.bashrc` $\rightarrow$ `backups/dotfiles/.bashrc`
- `~/.tmux.conf` $\rightarrow$ `backups/dotfiles/.tmux.conf`
- `~/.gitconfig` $\rightarrow$ `backups/dotfiles/.gitconfig`

## Subcommands
| Subcommand | Description | Safety Gate |
| :--- | :--- | :--- |
| `backup` | Copies active dotfiles from `$HOME` into `backups/dotfiles/` | Autonomous (Tier 2) |
| `diff` | Shows colorized diff between active dotfiles and repository copies | Autonomous (Tier 0) |
| `restore` | Restores repository dotfiles over active `$HOME` configuration | **Explicit Confirmation Required** |

## Safety & Invariant Rules
- The `restore` operation overwrites live user environment files; always run `diff` first and obtain explicit user consent before restoring.
```

- [ ] **Step 2: Run style audit on `dotfiles` skill**

Run: `agent-style review --audit-only .claude/skills/dotfiles/SKILL.md`
Expected: 0 violations.

- [ ] **Step 3: Commit Task 3 changes**

```bash
git add .claude/skills/dotfiles/SKILL.md
git commit -m "feat(skills): add dotfiles synchronization skill"
```

---

### Task 4: Create Missing `harness-check` Skill

**Files:**
- Create: `.claude/skills/harness-check/SKILL.md`

**Interfaces:**
- Consumes: `./scripts/harness_check.sh`, `tests/test_harness.sh`, `scripts/sync_agent_skills.sh`
- Produces: Complete SSOT skill for harness self-diagnostics and multi-agent validation

- [ ] **Step 1: Write `.claude/skills/harness-check/SKILL.md`**

Author the skill with YAML frontmatter, SDO trigger description, matrix validation stages (lifecycle hooks, 4-tier security guardrails, auto-healing linters, multi-agent symlink sync, settings JSON syntax), and diagnostic triage guide.

```markdown
---
name: harness-check
description: Use when running the harness self-test matrix, verifying lifecycle hooks, validating security guardrails, or checking multi-agent skill symlink integrity
---

# Harness Self-Check & Diagnostic Matrix Skill

Executes the complete end-to-end self-test suite and diagnostic matrix for the Claude Code Agent Harness architecture.

## Trigger Scenarios
- Validating harness stability after modifying lifecycle hooks or security rules
- Verifying zero-copy symlink propagation across multi-agent stores
- Validating syntax and configuration integrity of `.claude/settings.json`
- Pre-flight quality verification before branch merges and commits

## Invocation
```bash
/home/rizz/dev/os-manager/scripts/harness_check.sh
```

## Validation Matrix
1. **Hook & Guardrail Unit Test Suite (`tests/test_harness.sh`)**:
   - Session lifecycle hooks (`SessionStart`, `SessionEnd`)
   - PreToolUse 4-Tier Security Matrix (Tier 0, 1, 2 allowances; Tier 3 invariant blocks)
   - PostToolUse Auto-Healing Linting (`bash -n`, `shellcheck`, `jq empty`, `python3 -m py_compile`)
   - Failure telemetry logger and pre-compact state snapshots
2. **Multi-Agent SSOT Symlink Bridge (`scripts/sync_agent_skills.sh`)**:
   - Relative symlinks to `.agents/skills/` (Universal Agent standard)
   - Absolute symlinks to `~/.gemini/config/skills/` (Google Antigravity `agy`)
3. **Master Configuration Validation**:
   - JSON syntax and schema validation of `.claude/settings.json`

## Safety Classification
- **Tier 2 (Controlled System Operation)**: Pre-authorized self-check test runner.
```

- [ ] **Step 2: Run style audit on `harness-check` skill**

Run: `agent-style review --audit-only .claude/skills/harness-check/SKILL.md`
Expected: 0 violations.

- [ ] **Step 3: Commit Task 4 changes**

```bash
git add .claude/skills/harness-check/SKILL.md
git commit -m "feat(skills): add harness-check self-diagnostic skill"
```

---

### Task 5: Extend Test Suite for Skill Frontmatter & Symlink Validation

**Files:**
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `.claude/skills/*/SKILL.md`, `.agents/skills/*`, `~/.gemini/config/skills/*`
- Produces: Automated unit test assertions verifying 100% frontmatter compliance and 21-skill SSOT sync

- [ ] **Step 1: Update `tests/test_harness.sh`**

Add a dedicated test block verifying that:
1. Every directory in `.claude/skills/` contains a valid `SKILL.md`.
2. Every `SKILL.md` starts with a valid YAML frontmatter delimiter (`---`).
3. Every `SKILL.md` defines both `name:` and `description:` fields.
4. Description field begins with `Use when`.

```bash
echo "--- Testing Skills Frontmatter & SDO Compliance ---"
SKILL_ERRORS=0
for skill_file in "${WORKSPACE_ROOT}/.claude/skills"/*/SKILL.md; do
    skill_dir="$(dirname "${skill_file}")"
    skill_name="$(basename "${skill_dir}")"
    
    # Check frontmatter opening
    if ! head -n 1 "${skill_file}" | grep -q "^---"; then
        echo "  [FAIL] Missing YAML frontmatter in ${skill_name}/SKILL.md"
        SKILL_ERRORS=$((SKILL_ERRORS + 1))
        continue
    fi
    
    # Check name and description fields
    if ! grep -q "^name:" "${skill_file}" || ! grep -q "^description:" "${skill_file}"; then
        echo "  [FAIL] Missing name or description in ${skill_name}/SKILL.md"
        SKILL_ERRORS=$((SKILL_ERRORS + 1))
        continue
    fi
    
    # Check description starts with 'Use when' or 'You MUST use this'
    if ! grep -E -q 'description:.*(Use when|You MUST use this)' "${skill_file}"; then
        echo "  [FAIL] Description in ${skill_name}/SKILL.md does not follow SDO trigger convention"
        SKILL_ERRORS=$((SKILL_ERRORS + 1))
        continue
    fi
done
assert_exit_code "All Skills Frontmatter & SDO Compliance" 0 "${SKILL_ERRORS}"
```

- [ ] **Step 2: Run test suite to verify assertions pass**

Run: `./tests/test_harness.sh`
Expected: 15/15 tests passed.

- [ ] **Step 3: Commit Task 5 changes**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): add automated skill frontmatter and SDO validation tests"
```

---

### Task 6: Multi-Agent Synchronization, Full Harness Check, & Final Push

**Files:**
- Modify: `scripts/sync_agent_skills.sh` (if needed)
- Sync: `.agents/skills/*`, `~/.gemini/config/skills/*`

**Interfaces:**
- Consumes: All 21 standardized skills
- Produces: Clean git working tree, verified symlink bridges, and pushed remote commits

- [ ] **Step 1: Run Multi-Agent Symlink Synchronization**

Run: `./scripts/sync_agent_skills.sh`
Expected: Synchronized 21 skills to `.agents/skills/` and 21 skills to `~/.gemini/config/skills/`.

- [ ] **Step 2: Run Full Harness Self-Check Matrix**

Run: `./scripts/harness_check.sh`
Expected: All 15 unit tests pass, symlinks validate, and `.claude/settings.json` is clean.

- [ ] **Step 3: Run comprehensive agent-style review across all skills**

Run: `agent-style review --audit-only .claude/skills/*/SKILL.md`
Expected: 0 violations across all 21 skills.

- [ ] **Step 4: Push to GitHub**

```bash
git push origin main
```
