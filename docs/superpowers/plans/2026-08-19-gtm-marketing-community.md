# GTM Marketing & Community Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the 15-second VHS terminal recording tape (`vhs/demo.tape`), overhaul `README.md` with hero badges and quickstart box, author public launch playbooks (`playbooks/launch_show_hn.md` and `playbooks/launch_twitter_thread.md`), and configure community issue generator templates.

**Architecture:** Author a Charm VHS tape definition simulating Claude Code safety interception and status card rendering. Redesign `README.md` into a high-converting open-source landing page featuring hero media and 1-line curl quickstarts. Document execution playbooks for Show HN and X/Twitter technical launches.

**Tech Stack:** Markdown, Charm VHS tape syntax, ASCII art, GitHub issue forms.

**Spec:** `docs/superpowers/specs/2026-08-19-gtm-marketing-community-design.md`

## Global Constraints

- Verified copy-paste quickstart commands (`curl -fsSL https://raw.githubusercontent.com/0xrizz/os-manager/main/install.sh | bash`).
- Standard MIT license branding and GitHub badges.
- Strict Markdown formatting following repository writing style rules.
- Zero regression across all 55 master test harness assertions.

---

### Task 1: Create Marketing Assets Test Suite `tests/test_marketing_assets.sh`

**Files:**
- Create: `tests/test_marketing_assets.sh`

**Interfaces:**
- Consumes: `vhs/demo.tape`, `README.md`, `playbooks/launch_show_hn.md`, `playbooks/launch_twitter_thread.md`
- Produces: Runnable test suite returning 0 on pass, 1 on failure.

- [ ] **Step 1: Write the test suite**

Write `tests/test_marketing_assets.sh`:
```bash
#!/usr/bin/env bash
# tests/test_marketing_assets.sh - Unit tests for marketing assets & launch playbooks
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

assert_file_exists() {
    local test_name="$1"
    local file_path="$2"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ -f "${file_path}" ]; then
        echo "  [PASS] ${test_name} (file exists: ${file_path})"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (file missing: ${file_path})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

assert_file_contains() {
    local test_name="$1"
    local expected_pattern="$2"
    local file_path="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if grep -qE "${expected_pattern}" "${file_path}"; then
        echo "  [PASS] ${test_name} (matched pattern '${expected_pattern}')"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (missing pattern '${expected_pattern}')"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running Marketing Assets & GTM Test Suite"
echo "=================================================="

echo "--- 1. Testing Charm VHS Tape Definition ---"
VHS_FILE="${WORKSPACE_ROOT}/vhs/demo.tape"
assert_file_exists "VHS Tape Existence" "${VHS_FILE}"
assert_file_contains "VHS Output Configuration" "Output\s+assets/demo.gif" "${VHS_FILE}"
assert_file_contains "VHS Command Simulation" "rm -rf" "${VHS_FILE}"
assert_file_contains "VHS Diag Command Simulation" "/diag" "${VHS_FILE}"

echo "--- 2. Testing README Hero & Quickstart Structure ---"
README_FILE="${WORKSPACE_ROOT}/README.md"
assert_file_exists "README Existence" "${README_FILE}"
assert_file_contains "README Hero Tagline" "Run Claude Code autonomously without fear" "${README_FILE}"
assert_file_contains "README 1-Line Curl Quickstart" "curl -fsSL.*install\.sh.*bash" "${README_FILE}"
assert_file_contains "README CI Badges" "img\.shields\.io" "${README_FILE}"

echo "--- 3. Testing Launch Playbooks ---"
HN_PLAYBOOK="${WORKSPACE_ROOT}/playbooks/launch_show_hn.md"
assert_file_exists "Show HN Playbook Existence" "${HN_PLAYBOOK}"
assert_file_contains "Show HN Title" "Show HN: os-manager" "${HN_PLAYBOOK}"

TWITTER_PLAYBOOK="${WORKSPACE_ROOT}/playbooks/launch_twitter_thread.md"
assert_file_exists "Twitter Thread Playbook Existence" "${TWITTER_PLAYBOOK}"
assert_file_contains "Twitter Thread 5-Post Structure" "Post 5" "${TWITTER_PLAYBOOK}"

echo "=================================================="
echo "Results: ${PASSED_TESTS}/${TOTAL_TESTS} passed, ${FAILED_TESTS} failed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
exit 0
```

- [ ] **Step 2: Make executable and verify failure**

Run: `chmod +x tests/test_marketing_assets.sh && ./tests/test_marketing_assets.sh`
Expected: FAIL due to missing `vhs/demo.tape`, `launch_show_hn.md`, and `launch_twitter_thread.md`.

- [ ] **Step 3: Commit test suite**

```bash
git add tests/test_marketing_assets.sh
git commit -m "test(marketing): add test suite for marketing assets and launch playbooks"
```

---

### Task 2: Author Charm VHS Recording Script `vhs/demo.tape`

**Files:**
- Create: `vhs/demo.tape`

**Interfaces:**
- Consumes: Terminal session commands.
- Produces: Charm VHS recording specification targeting `assets/demo.gif`.

- [ ] **Step 1: Write `vhs/demo.tape`**

Write `vhs/demo.tape`:
```text
# vhs/demo.tape - Charm VHS terminal recording script
Output assets/demo.gif

Set FontSize 16
Set Width 1200
Set Height 640
Set Theme "Catppuccin Mocha"
Set Padding 20

Type "claude"
Enter
Sleep 1s

# Scenario 1: Intercepting risky operation into auto-sandbox
Type "rm -rf ./temp_build"
Enter
Sleep 1.5s

# Scenario 2: Running instant diagnostics dashboard
Type "/diag"
Enter
Sleep 3s
```

- [ ] **Step 2: Verify VHS tape file creation**

Run: `./tests/test_marketing_assets.sh`
Expected: Section 1 assertions pass.

- [ ] **Step 3: Commit VHS tape**

```bash
git add vhs/demo.tape
git commit -m "chore(marketing): add Charm VHS demo tape definition"
```

---

### Task 3: Overhaul `README.md` with Hero Hierarchy & 1-Line Quickstart

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: High-converting copy and ASCII architecture maps.
- Produces: Clean, scannable open-source repository landing page.

- [ ] **Step 1: Update `README.md`**

Update `README.md`:
```markdown
# os-manager

<p align="center">
  <a href="https://github.com/0xrizz/os-manager/actions"><img src="https://img.shields.io/github/actions/workflow/status/0xrizz/os-manager/ci.yml?branch=main&label=CI&logo=github" alt="CI Status"></a>
  <a href="https://pypi.org/project/os-manager/"><img src="https://img.shields.io/pypi/v/os-manager?color=blue&logo=pypi" alt="PyPI Version"></a>
  <a href="https://github.com/0xrizz/os-manager/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT"></a>
  <a href="https://github.com/0xrizz/os-manager"><img src="https://img.shields.io/badge/tests-55%2F55%20passing-brightgreen" alt="Tests"></a>
</p>

<p align="center">
  <strong>Run Claude Code autonomously without fear of host destruction.</strong><br>
  Open-source governance harness, 4-tier security matrix, auto-sandbox fallback, and background telemetry engine across Linux, WSL2, and macOS.
</p>

---

## ⚡ Quickstart (10 Seconds)

Install and configure hooks, guardrails, and slash commands in a single command:

```bash
curl -fsSL https://raw.githubusercontent.com/0xrizz/os-manager/main/install.sh | bash
```

Or install via Python toolchain:

```bash
uv tool install os-manager
osm check
```

---

## 🛡️ Core Features

- **4-Tier Security Matrix**: Deterministically blocks host sabotage (`/mnt/c/Windows`, `/etc/shadow`) with hard zero-trust vetoes (Exit Code 2).
- **Auto-Sandbox Fallback**: Seamlessly reroutes risky operations (`rm -rf`, heavy purges) into rootless Podman containers without aborting turns.
- **Workstation Performance**: Automated VHDX compaction, zero 9P latency enforcement on ext4, and fast cache cleanup.
- **Background Observability**: Built-in Prometheus metrics exporter (`127.0.0.1:9100`) and nanosecond hook latency tracing.
- **Multi-Agent SSOT Bridge**: Zero-copy relative symlinks synchronizing skills across Claude Code, Universal Agent, and Google Antigravity.

---

## 🏛️ Harness Architecture

```text
 ══════════════════════════════════════════════════════════════════════════════════════════════════
                                CLAUDE-FIRST AGENT HARNESS TOPOLOGY                                  
 ══════════════════════════════════════════════════════════════════════════════════════════════════
                                               │
 ┌─────────────────────────────────────────────▼──────────────────────────────────────────────────┐
 │ HARNESS CONFIGURATION & GOVERNANCE LAYER                                                       │
 │ • .claude/settings.json (Permissions, Env, Hook Registrations)                                 │
 │ • CLAUDE.md & .claude/rules/ (WSL Boundaries, Safety Tiers, Error Recovery Protocols)         │
 └─────────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                               │
        ┌──────────────────────────────────────┼──────────────────────────────────────┐
        ▼                                      ▼                                      ▼
 ┌──────────────┐                       ┌──────────────┐                       ┌──────────────┐
 │  LIFECYCLE   │                       │    CUSTOM    │                       │ MULTI-AGENT  │
 │    HOOKS     │                       │   COMMANDS   │                       │ INTEROP &    │
 │    ENGINE    │                       │   & SKILLS   │                       │  SUBAGENTS   │
 ├──────────────┤                       ├──────────────┤                       ├──────────────┤
 │•SessionStart │                       │• /diag       │                       │•.claude/     │
 │•PreToolUse   │                       │• /clean      │                       │  skills/     │
 │•PostToolUse  │                       │• /upgrade    │                       │•.agents/     │
 │•PostFailure  │                       │• /snapshot   │                       │  skills/     │
 │•PreCompact   │                       │• /dotfiles   │                       │•~/.gemini/   │
 │•SessionEnd   │                       │• /pair       │                       │  config/     │
 │              │                       │• /harness-   │                       │  skills/     │
 │              │                       │  check       │                       │•.claude/     │
 │              │                       │              │                       │  agents/     │
 └──────────────┘                       └──────────────┘                       └──────────────┘
```

---

## 💻 Custom Slash Commands

- `/diag`: Compact Unicode health dashboard card and system status.
- `/clean`: Safe space reclamation across APT, UV, PNPM, Bun, and `/tmp`.
- `/upgrade`: Coordinated toolchain and runtime updates.
- `/snapshot`: Disaster recovery point-in-time distro backups.
- `/pair`: Spawns paired multi-agent Tmux workspace (Claude Code + Antigravity).

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
```

- [ ] **Step 2: Verify README assertions**

Run: `./tests/test_marketing_assets.sh`
Expected: Section 2 assertions pass.

- [ ] **Step 3: Commit README overhaul**

```bash
git add README.md
git commit -m "docs(readme): overhaul landing page with hero badges and 1-line quickstart"
```

---

### Task 4: Author Launch Playbooks `playbooks/launch_show_hn.md` & `playbooks/launch_twitter_thread.md`

**Files:**
- Create: `playbooks/launch_show_hn.md`
- Create: `playbooks/launch_twitter_thread.md`

**Interfaces:**
- Consumes: Positioning narrative and technical mechanics.
- Produces: Ready-to-publish launch copy for Hacker News and X/Twitter.

- [ ] **Step 1: Write `playbooks/launch_show_hn.md`**

Write `playbooks/launch_show_hn.md`:
```markdown
# Show HN Launch Playbook

## Submission Details

- **Title**: Show HN: os-manager – Open-source safety harness and sandbox for Claude Code
- **URL**: https://github.com/0xrizz/os-manager

## First Comment (Maker Comment)

Hey HN,

I built `os-manager` because running autonomous AI coding loops (like Claude Code) on developer workstations creates a real dilemma: either you constantly click permission prompts, or you grant broad execution rights and risk host filesystem churn or runaway disk bloat.

`os-manager` is a lightweight governance harness and control plane that wraps Claude Code with deterministic POSIX lifecycle hooks:

1. **4-Tier Security Matrix**: Intercepts tool calls deterministically. Host-level sabotage (e.g. `/mnt/c/Windows`, `/etc/shadow`) is hard-blocked with Exit Code 2.
2. **Auto-Sandbox Fallback**: Risky commands (`rm -rf ./temp`, heavy package purges) automatically reroute into disposable rootless Podman containers, keeping the agent loop running without host blast radius.
3. **Workstation Hygiene**: Reclaims VHDX disk space on WSL2, enforces native ext4 storage boundaries, and exports Prometheus metrics (`:9100`).
4. **Zero-Secret Distribution**: Published to PyPI via OIDC Trusted Publishing with automated SHA256 checksum generation.

Quickstart:
```bash
curl -fsSL https://raw.githubusercontent.com/0xrizz/os-manager/main/install.sh | bash
```

Everything is open source under MIT, with a 55-assertion test suite running on Linux, WSL2, and macOS.

I'd love feedback on what additional guardrails or workstation automation profiles you'd like to see!
```

- [ ] **Step 2: Write `playbooks/launch_twitter_thread.md`**

Write `playbooks/launch_twitter_thread.md`:
```markdown
# X / Twitter Technical Launch Thread

## Post 1 (Hook & Media)
What happens when you let an autonomous AI coding agent run for 6 hours? Without guardrails: catastrophic host churn and virtual disk bloat.

Introducing `os-manager`: The open-source safety harness and control plane for Claude Code. 🛡️⚡

[Attach demo.gif]

## Post 2 (The Dilemma)
The problem: Developers face two extremes with AI coding agents:
1. Friction-heavy permission prompts every 30 seconds
2. Unconstrained execution that risks accidental `rm -rf` or host corruption

`os-manager` introduces a deterministic 4-tier security matrix to bridge this gap.

## Post 3 (Auto-Sandbox Architecture)
Instead of failing with red error walls, `os-manager` reroutes risky operations into disposable, rootless Podman containers.

Host sabotage is hard-vetoed. Risky operations run isolated. Your agent workflow never breaks.

## Post 4 (Workstation Performance & Hygiene)
Beyond safety, `os-manager` keeps your dev machine lean:
• Automated WSL2 VHDX compaction (>10GB reclaimed)
• Zero 9P virtualization lag on ext4
• Built-in Prometheus metrics daemon (`:9100`)
• Nanosecond hook latency tracing (<50ms P99)

## Post 5 (Get Started & Open Source)
Try `os-manager` in 10 seconds:

```bash
curl -fsSL https://raw.githubusercontent.com/0xrizz/os-manager/main/install.sh | bash
```

100% open source under MIT. 55/55 tests passing.
⭐ Star on GitHub: https://github.com/0xrizz/os-manager
```

- [ ] **Step 3: Verify all test assertions**

Run: `./tests/test_marketing_assets.sh`
Expected: All tests in `tests/test_marketing_assets.sh` pass.

- [ ] **Step 4: Commit launch playbooks**

```bash
git add playbooks/launch_show_hn.md playbooks/launch_twitter_thread.md
git commit -m "docs(marketing): author Show HN and Twitter launch playbooks"
```

---

### Task 5: Master Harness Integration & Full Verification

**Files:**
- Modify: `tests/test_harness.sh`

**Interfaces:**
- Consumes: `tests/test_marketing_assets.sh`
- Produces: 0 regressions across master test suite.

- [ ] **Step 1: Integrate `test_marketing_assets.sh` into `tests/test_harness.sh`**

Add assertion block to `tests/test_harness.sh`:
```bash
echo "--- Testing Marketing Assets & GTM Suite ---"
set +e
"${WORKSPACE_ROOT}/tests/test_marketing_assets.sh" > /dev/null 2>&1
assert_exit_code "Marketing Assets & GTM Unit Tests" 0 $?
set -e
```

- [ ] **Step 2: Run master test suite and self-check**

Run: `./tests/test_harness.sh && ./scripts/harness_check.sh`
Expected: All tests pass (58+ assertions).

- [ ] **Step 3: Commit integration**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate marketing assets test suite into master harness"
```
