# Multi-Agent Harness Isolation & Zero-Host Pollution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure 100% workspace-scoped isolation for all multi-agent components, preventing unintended file mutations or automatic symlink exports to global user directories (`~/.claude/skills/`, `~/.gemini/config/skills/`, `~/.agent/`, `~/.agents/`).

**Architecture:** Refactor `scripts/sync_agent_skills.sh` to validate workspace skills locally by default and gate global export behind `--global`. Clean obsolete `.agents/` workspace mirror and purge global symlink references from `$HOME`. Add automated isolation assertion tests in `tests/test_harness_isolation.sh` and integrate into the master test harness.

**Tech Stack:** Bash 5+, POSIX Shell, Pytest / Shell Testing.

**Spec:** `docs/superpowers/specs/2026-08-25-multi-agent-harness-isolation-design.md`

## Global Constraints

- **Single Source of Truth (SSOT)**: `.claude/skills/` is the sole SSOT, strictly scoped to the repository workspace.
- **Zero Implicit Global Promotion**: No script or hook may write to `${HOME}/.claude/skills` or `${HOME}/.gemini/config/skills` unless explicitly passed `--global`.
- **Zero Dangling Symlinks**: Global directories must contain zero broken or repository-referencing symlinks by default.
- **Master Harness Integrity**: All 81+ assertions in `./tests/test_harness.sh` must remain 100% passing.

---

## File Structure & Module Map

```text
scripts/
└── sync_agent_skills.sh               # Modified: Default local workspace validation, gated --global export

CLAUDE.md                              # Modified: Updated SSOT & isolation governance rules

tests/
├── tmux/test_skill_docs.sh            # Modified: Targets .claude/skills/ instead of deprecated .agents/skills/
├── test_harness_isolation.sh          # Create: Automated isolation & host pollution validation suite
└── test_harness.sh                    # Modified: Integrate test_harness_isolation.sh into master suite

docs/superpowers/specs/
└── 2026-08-25-multi-agent-harness-isolation-design.md  # Spec documentation
```

---

### Task 1: Create Automated Harness Isolation Test Suite

**Files:**
- Create: `tests/test_harness_isolation.sh`
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `scripts/sync_agent_skills.sh`, `scripts/hooks/session_preflight.sh`, `~/.claude/skills`, `~/.gemini/config/skills`
- Produces: Executable shell test suite asserting zero unexpected file creation in `$HOME` during default sync and preflight operations.

- [ ] **Step 1: Write the failing test**

Create `tests/test_harness_isolation.sh`:

```bash
#!/usr/bin/env bash
# tests/test_harness_isolation.sh - Validate zero-host pollution and workspace isolation
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GLOBAL_CLAUDE="${HOME}/.claude/skills"
GLOBAL_GEMINI="${HOME}/.gemini/config/skills"

echo "==> [ISO-01] Testing sync_agent_skills.sh default workspace isolation..."
# Count symlinks in global dirs before execution
BEFORE_CLAUDE_LINKS=$(find "${GLOBAL_CLAUDE}" -maxdepth 1 -type l 2>/dev/null | wc -l || echo 0)
BEFORE_GEMINI_LINKS=$(find "${GLOBAL_GEMINI}" -maxdepth 1 -type l 2>/dev/null | wc -l || echo 0)

"${WORKSPACE_ROOT}/scripts/sync_agent_skills.sh" >/dev/null

AFTER_CLAUDE_LINKS=$(find "${GLOBAL_CLAUDE}" -maxdepth 1 -type l 2>/dev/null | wc -l || echo 0)
AFTER_GEMINI_LINKS=$(find "${GLOBAL_GEMINI}" -maxdepth 1 -type l 2>/dev/null | wc -l || echo 0)

if [ "${BEFORE_CLAUDE_LINKS}" -ne "${AFTER_CLAUDE_LINKS}" ] || [ "${BEFORE_GEMINI_LINKS}" -ne "${AFTER_GEMINI_LINKS}" ]; then
    echo "FAIL: sync_agent_skills.sh modified global directories without --global flag"
    exit 1
fi
echo "PASS: sync_agent_skills.sh does not pollute global directories."

echo "==> [ISO-02] Testing session_preflight.sh execution isolation..."
"${WORKSPACE_ROOT}/scripts/hooks/session_preflight.sh" >/dev/null

FINAL_CLAUDE_LINKS=$(find "${GLOBAL_CLAUDE}" -maxdepth 1 -type l 2>/dev/null | wc -l || echo 0)
FINAL_GEMINI_LINKS=$(find "${GLOBAL_GEMINI}" -maxdepth 1 -type l 2>/dev/null | wc -l || echo 0)

if [ "${FINAL_CLAUDE_LINKS}" -ne "${BEFORE_CLAUDE_LINKS}" ] || [ "${FINAL_GEMINI_LINKS}" -ne "${BEFORE_GEMINI_LINKS}" ]; then
    echo "FAIL: session_preflight.sh caused global directory pollution"
    exit 1
fi
echo "PASS: session_preflight.sh maintains workspace isolation."

echo "==> [ISO-03] Asserting absence of deprecated ~/.agent and ~/.agents directories..."
if [ -d "${HOME}/.agent" ] || [ -d "${HOME}/.agents" ]; then
    echo "FAIL: Deprecated ~/.agent or ~/.agents directory found in home"
    exit 1
fi
echo "PASS: No deprecated agent directories present."

echo "==> [ISO-04] Asserting absence of workspace .agents directory..."
if [ -d "${WORKSPACE_ROOT}/.agents" ]; then
    echo "FAIL: Deprecated .agents directory found in workspace"
    exit 1
fi
echo "PASS: Workspace .agents mirror absent."

echo "✓ All Harness Isolation checks passed."
exit 0
```

- [ ] **Step 2: Run test to verify behavior**

Run: `bash tests/test_harness_isolation.sh`
Expected: PASS

- [ ] **Step 3: Integrate into master test harness**

Modify `tests/test_harness.sh` to include `tests/test_harness_isolation.sh`:

```bash
echo "--- Testing Multi-Agent Harness Isolation Suite ---"
"${WORKSPACE_ROOT}/tests/test_harness_isolation.sh" > /dev/null 2>&1
assert_exit_code "test_harness_isolation.sh complete suite" 0 $?
```

- [ ] **Step 4: Run master test harness to verify integration**

Run: `./tests/test_harness.sh`
Expected: 82/82 passed

---

### Task 2: Commit Multi-Agent Isolation Changes and Specs

**Files:**
- Modify: `CLAUDE.md`
- Modify: `scripts/sync_agent_skills.sh`
- Modify: `tests/tmux/test_skill_docs.sh`
- Modify: `tests/test_harness.sh`
- Create: `tests/test_harness_isolation.sh`
- Create: `docs/superpowers/specs/2026-08-25-multi-agent-harness-isolation-design.md`
- Create: `docs/superpowers/plans/2026-08-25-multi-agent-harness-isolation.md`

- [ ] **Step 1: Verify git status and diff**

Run: `git status -s`

- [ ] **Step 2: Stage and commit all isolation artifacts**

```bash
git add CLAUDE.md scripts/sync_agent_skills.sh tests/tmux/test_skill_docs.sh tests/test_harness.sh tests/test_harness_isolation.sh docs/superpowers/specs/2026-08-25-multi-agent-harness-isolation-design.md docs/superpowers/plans/2026-08-25-multi-agent-harness-isolation.md
git commit -m "feat(governance): enforce workspace multi-agent isolation and zero-host pollution"
```

- [ ] **Step 3: Run post-commit harness check**

Run: `./scripts/harness_check.sh`
Expected: ALL HARNESS COMPONENT CHECKS PASSED
