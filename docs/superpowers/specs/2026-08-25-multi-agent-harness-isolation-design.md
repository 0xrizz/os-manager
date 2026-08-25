# Specification: Multi-Agent Harness Isolation & Zero-Host Pollution Architecture

- **Date:** 2026-08-25
- **Scope:** Workspace Skill Scoping, Elimination of Redundant Global Directories, and Deterministic Harness Isolation
- **Status:** Proposed / Active Specification
- **Author:** Lead Systems Engineer & Open-Source Governance Architect
- **Target Repository:** `os-manager`

---

## 1. Executive Summary & Problem Statement

In previous iterations, `os-manager` attempted universal interoperability across multi-agent harnesses (Claude Code, Google Antigravity `agy`, Universal Agent) by automatically creating symlinks from the workspace `.claude/skills/` to user global configuration directories (`~/.gemini/config/skills/` and `~/.claude/skills/`) and maintaining separate user-level directories (`~/.agent/`, `~/.agents/`).

### Empirical Deficiencies Identified:
1. **Implicit Global Pollution**: Project-specific development skills, test utilities, and experimental workflows were automatically promoted to the global user environment upon every session start (`session_preflight.sh`) and harness verification (`harness_check.sh`).
2. **Configuration Fragmentation & Redundancy**: The coexistence of `~/.agent/`, `~/.agents/`, `~/.claude/`, and `~/.gemini/` in `$HOME` caused confusion regarding skill resolution hierarchy and created dangling symlinks when workspaces were renamed or relocated.
3. **Breach of Open-Source Invariants**: An open-source harness must never mutate the host system's global agent configuration without explicit, user-initiated opt-in.

---

## 2. Architectural Invariants & Scope Boundaries

```text
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │                           USER HOST ENVIRONMENT                             │
 │                                                                             │
 │   ~/.claude/skills/              ~/.gemini/config/skills/                   │
 │   (Global Claude Skills)         (Global Antigravity Skills)                │
 │   [find-skills, custom...]       [context7-mcp, custom...]                  │
 └─────────────────────────────────────────────────────────────────────────────┘
                                       ▲
                                       │ (Explicit opt-in ONLY: --global)
                                       │
 ┌─────────────────────────────────────┴───────────────────────────────────────┐
 │                     WORKSPACE DOMAIN (os-manager)                           │
 │                                                                             │
 │   .claude/skills/ (SSOT) ───────────► Scoped to active repository only      │
 │   • 24 project-specific skills                                              │
 │   • No auto-export to $HOME                                                 │
 │   • No workspace .agents/ directory sprawl                                  │
 └─────────────────────────────────────────────────────────────────────────────┘
```

### Core Invariants:

1. **Workspace-Scoped SSOT**:
   - `.claude/skills/` serves as the Single Source of Truth (SSOT) strictly within the local workspace.
   - Subagent workflows operating within this workspace resolve skills exclusively from `.claude/skills/`.

2. **Zero Implicit Global Promotion**:
   - Lifecycle hooks (`SessionStart`, `PreToolUse`, `PostToolUse`), preflight scripts (`session_preflight.sh`), post-bootstrap routines (`post_bootstrap.sh`), and self-checks (`harness_check.sh`) are strictly prohibited from writing or linking into `~/.claude/skills/`, `~/.gemini/config/skills/`, or any other directory under `${HOME}/`.
   - Global skill promotion is reserved as an explicit manual action via `./scripts/sync_agent_skills.sh --global`.

3. **Elimination of Deprecated Global Directories**:
   - The directories `~/.agent/` and `~/.agents/` are formally deprecated and eliminated.
   - The workspace-level `.agents/` symlink mirror is removed to prevent redundant metadata synchronization.

---

## 3. Component Design & Behavioral Contracts

### 3.1 `scripts/sync_agent_skills.sh`
- **Default Mode (No Args)**:
  - Validates the integrity and count of skills within `.claude/skills/`.
  - Exits 0 without creating or modifying any symlinks outside `${WORKSPACE_ROOT}`.
- **Global Opt-In Mode (`--global`)**:
  - Requires explicit invocation by the user.
  - Cleans stale symlinks in `~/.claude/skills/` and `~/.gemini/config/skills/`.
  - Creates deterministic symlinks to `.claude/skills/*`.

### 3.2 Preflight & Self-Check Integration
- `scripts/hooks/session_preflight.sh`: Executes `sync_agent_skills.sh` in read-only validation mode.
- `scripts/harness_check.sh`: Verifies that `.claude/skills/` contains valid markdown frontmatter without modifying `$HOME`.
- `scripts/post_bootstrap.sh`: Verifies local permissions and timers without generating global symlinks.

### 3.3 Documentation & Agent Rules
- `CLAUDE.md`: Documents workspace isolation as a core governance invariant.
- Subagent definitions (`.claude/agents/*.md`): Refactored to reference `.claude/skills/` instead of global or `.agents/` paths.

---

## 4. Verification & Quality Gates

The implementation must satisfy the following automated assertions:

| Check ID | Verification Target | Expected Behavior |
|---|---|---|
| **ISO-01** | `scripts/sync_agent_skills.sh` execution | Exits 0, touches 0 files in `$HOME`. |
| **ISO-02** | `scripts/hooks/session_preflight.sh` | Completes with exit 0; `$HOME/.gemini` and `$HOME/.claude` unmodified. |
| **ISO-03** | `./tests/test_harness.sh` | 81/81 assertions pass, zero path leaks detected. |
| **ISO-04** | Global symlink inspection | `find ~/.gemini/config/skills ~/.claude/skills -type l` contains zero references to the repository path. |

---

## 5. Rollout & Migration Steps

1. **Phase 1 (Completed)**: Purge `~/.agent`, `~/.agents`, and dangling global symlinks.
2. **Phase 2 (Completed)**: Update `sync_agent_skills.sh` and `CLAUDE.md` to enforce default isolation.
3. **Phase 3 (Next Step)**: Formalize this specification in the repository docs and transition to implementation plan review.
