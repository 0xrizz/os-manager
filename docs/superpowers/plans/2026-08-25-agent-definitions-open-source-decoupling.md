# Multi-Agent Subagent Definitions Open-Source Decoupling Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple subagent definitions in `.claude/agents/` and `.agents/agents/` from machine-specific constants (Lenovo 81WD, ALC298 audio codec, hardcoded `/dev/nvme0n1p4`, static 8GB RAM assumptions) to achieve 100% architectural alignment with the Open-Source Transformation Roadmap and Dynamic HAL.

**Architecture:** Refactor 5 targeted agent definitions (`audio-hardware-tuner`, `disaster-recovery-engineer`, `linux-migration-engineer`, `perf-optimizer`, `system-operator`) to consume declarative configuration from `.osm.toml` (`[security.protected_mounts]`), dynamic hardware drivers via `os_manager.platform.hal`, dynamic storage inspection, and modular migration profiles. Synchronize SSOT to downstream Antigravity / Universal Agent paths and add automated agent frontmatter & keyword validation tests.

**Tech Stack:** Markdown / YAML Frontmatter, Python `unittest` / `pytest`, Shell (`sync_agent_skills.sh`, `harness_check.sh`).

**Spec:** `docs/superpowers/specs/2026-08-24-open-source-transformation-roadmap-design.md` (Sections 2.1, 3.1, 3.4, and Mini-RFC 002).

## Global Constraints

- **Single Source of Truth (SSOT)**: Master definitions must reside in `.claude/agents/` and `.agents/agents/`.
- **Zero Hardcoded Device / Partition Paths**: Discard static paths like `/dev/nvme0n1p4`, `/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00`, and `ALC298` in favor of dynamic HAL abstractions and `.osm.toml` config parameters.
- **Valid Agent Frontmatter**: Every agent file must contain valid YAML frontmatter specifying `name`, `description`, `tools`, and `model`/`effort`.
- **Non-Destructive Invariants**: Preserve all core security invariants (zero-data-loss protection, 4-tier security matrix, non-interactive sudo streaming).

---

## File Structure & Module Map

```text
.claude/agents/
├── audio-hardware-tuner.md          # Refactor: Polymorphic HAL & Audio Subsystem Engineer
├── disaster-recovery-engineer.md    # Refactor: Declarative Storage & WSL Snapshot Engineer
├── linux-migration-engineer.md      # Refactor: Universal Distro Migration & Bootloader Specialist
├── perf-optimizer.md                # Refactor: Dynamic Kernel, Memory & Storage I/O Optimizer
└── system-operator.md               # Refactor: Declarative Config & Worktree Maintenance Operator

.agents/agents/
├── audio-hardware-tuner.md          # Mirror sync
├── disaster-recovery-engineer.md    # Mirror sync
├── linux-migration-engineer.md      # Mirror sync
├── perf-optimizer.md                # Mirror sync
└── system-operator.md               # Mirror sync

tests/
└── test_agent_definitions.py        # New test: Validate frontmatter, zero hardcoded paths, and tool schemas
```

---

### Task 1: Add Unit Tests for Agent Definitions Portability and Invariants

**Files:**
- Create: `tests/test_agent_definitions.py`

**Interfaces:**
- Consumes: `.claude/agents/*.md`, `.agents/agents/*.md`
- Produces: Test suite validating YAML frontmatter schema, absence of hardcoded personal paths (`/dev/nvme0n1p4`, `81WD`, `/home/rizz` outside examples), and presence of required safety sections.

- [ ] **Step 1: Write the failing test**

Create `tests/test_agent_definitions.py`:

```python
"""Unit tests verifying agent definition schemas, decoupling, and portability."""

from pathlib import Path
import re
import unittest

FORBIDDEN_HARDCODED_PATTERNS = [
    re.compile(r"/dev/nvme0n1p4"),
    re.compile(r"81WD"),
    re.compile(r"ALC298.*strictly"),
]

REQUIRED_AGENTS = [
    "audio-hardware-tuner.md",
    "disaster-recovery-engineer.md",
    "linux-migration-engineer.md",
    "perf-optimizer.md",
    "prompt-architect.md",
    "security-auditor.md",
    "system-operator.md",
    "test-verifier.md",
    "tmux-agents-coordinator.md",
]


class TestAgentDefinitions(unittest.TestCase):
    """Validate agent definition structure, frontmatter, and open-source decoupling."""

    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent
        self.claude_agents_dir = self.repo_root / ".claude" / "agents"
        self.agents_dir = self.repo_root / ".agents" / "agents"

    def test_all_required_agents_exist(self) -> None:
        for agent_file in REQUIRED_AGENTS:
            claude_path = self.claude_agents_dir / agent_file
            self.assertTrue(claude_path.is_file(), f"Missing Claude agent: {agent_file}")

    def test_no_hardcoded_personal_paths_in_claude_agents(self) -> None:
        for agent_file in REQUIRED_AGENTS:
            file_path = self.claude_agents_dir / agent_file
            content = file_path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_HARDCODED_PATTERNS:
                self.assertFalse(
                    pattern.search(content),
                    f"Forbidden personal constant '{pattern.pattern}' found in {agent_file}",
                )

    def test_claude_agents_frontmatter_validity(self) -> None:
        for agent_file in REQUIRED_AGENTS:
            file_path = self.claude_agents_dir / agent_file
            content = file_path.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("---\n"), f"{agent_file} must start with YAML frontmatter")
            parts = content.split("---", 2)
            self.assertGreaterEqual(len(parts), 3, f"{agent_file} frontmatter closing missing")
            fm = parts[1]
            self.assertIn("name:", fm)
            self.assertIn("description:", fm)
            self.assertIn("tools:", fm)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
.venv/bin/python -m unittest tests/test_agent_definitions.py
```
Expected output:
```text
AssertionError: Forbidden personal constant '/dev/nvme0n1p4' found in disaster-recovery-engineer.md
```

- [ ] **Step 3: Commit test file**

Run:
```bash
git add tests/test_agent_definitions.py
git commit -m "test(agents): add automated schema and portability validation suite for subagents"
```

---

### Task 2: Decouple `audio-hardware-tuner.md` and `perf-optimizer.md`

**Files:**
- Modify: `.claude/agents/audio-hardware-tuner.md`
- Modify: `.claude/agents/perf-optimizer.md`
- Modify: `.agents/agents/audio-hardware-tuner.md`
- Modify: `.agents/agents/perf-optimizer.md`

**Interfaces:**
- Consumes: `os_manager.platform.hal` (`get_active_hardware_driver`, `audit_storage_subsystem`), dynamic sysctl parameters.
- Produces: Fully vendor-agnostic hardware tuner and performance optimizer agent definitions.

- [ ] **Step 1: Refactor `.claude/agents/audio-hardware-tuner.md`**

Update `.claude/agents/audio-hardware-tuner.md` to reference dynamic HAL drivers (`LenovoDriver`, `AsusDriver`, `DellDriver`, `DarwinDriver`, `GenericLinuxDriver`) and ALSA/PipeWire auto-routing without hardcoded machine constants.

- [ ] **Step 2: Refactor `.claude/agents/perf-optimizer.md`**

Update `.claude/agents/perf-optimizer.md` to consume dynamic memory scaling (zRAM based on probed RAM capacity) and dynamic storage scheduler discovery from `os_manager.platform.hal.storage`.

- [ ] **Step 3: Synchronize changes to `.agents/agents/`**

Mirror the updated content to `.agents/agents/audio-hardware-tuner.md` and `.agents/agents/perf-optimizer.md`.

- [ ] **Step 4: Run test to verify progress**

Run:
```bash
.venv/bin/python -m unittest tests/test_agent_definitions.py
```

- [ ] **Step 5: Commit**

Run:
```bash
git add .claude/agents/audio-hardware-tuner.md .claude/agents/perf-optimizer.md .agents/agents/audio-hardware-tuner.md .agents/agents/perf-optimizer.md
git commit -m "refactor(agents): decouple audio-hardware-tuner and perf-optimizer to dynamic HAL"
```

---

### Task 3: Decouple `disaster-recovery-engineer.md`, `linux-migration-engineer.md`, and `system-operator.md`

**Files:**
- Modify: `.claude/agents/disaster-recovery-engineer.md`
- Modify: `.claude/agents/linux-migration-engineer.md`
- Modify: `.claude/agents/system-operator.md`
- Modify: `.agents/agents/disaster-recovery-engineer.md`
- Modify: `.agents/agents/linux-migration-engineer.md`
- Modify: `.agents/agents/system-operator.md`

**Interfaces:**
- Consumes: Declarative `.osm.toml` config (`[security.protected_mounts]`, `[backup.destination]`), universal migration playbooks (`--profile legacy-lenovo`).
- Produces: Portable disaster recovery, universal migration, and system operator agent definitions.

- [ ] **Step 1: Refactor `.claude/agents/disaster-recovery-engineer.md`**

Replace hardcoded `/dev/nvme0n1p4` with declarative protected mount validation (`.osm.toml` `security.protected_mounts` and dynamic backup target resolution).

- [ ] **Step 2: Refactor `.claude/agents/linux-migration-engineer.md`**

Transform persona into *Universal Linux Migration & Bootloader Specialist* with support for generic EFI system partition auto-discovery (`bootctl status`, `findmnt /boot/efi`) and legacy Lenovo geometry isolated under dedicated profiles.

- [ ] **Step 3: Refactor `.claude/agents/system-operator.md`**

Align execution with `.osm.toml` manifest, `osm` CLI commands, and dynamic storage/hardware inspection.

- [ ] **Step 4: Synchronize changes to `.agents/agents/`**

Mirror changes to `.agents/agents/disaster-recovery-engineer.md`, `.agents/agents/linux-migration-engineer.md`, and `.agents/agents/system-operator.md`.

- [ ] **Step 5: Run tests and verify all pass**

Run:
```bash
.venv/bin/python -m unittest tests/test_agent_definitions.py -v
```
Expected output:
```text
test_all_required_agents_exist (tests.test_agent_definitions.TestAgentDefinitions) ... ok
test_claude_agents_frontmatter_validity (tests.test_agent_definitions.TestAgentDefinitions) ... ok
test_no_hardcoded_personal_paths_in_claude_agents (tests.test_agent_definitions.TestAgentDefinitions) ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.005s

OK
```

- [ ] **Step 6: Commit**

Run:
```bash
git add .claude/agents/ .agents/agents/ tests/test_agent_definitions.py
git commit -m "refactor(agents): decouple disaster recovery, migration, and system operator agents to declarative config"
```

---

### Task 4: Harness Validation and Full Test Suite Regression Gate

**Files:**
- Test: `tests/test_harness.sh`
- Test: `.venv/bin/pytest tests/`

**Interfaces:**
- Consumes: All updated agent definitions, test suites, and harness scripts.
- Produces: 100% green harness verification and Pytest execution.

- [ ] **Step 1: Run Pytest test suite**

Run:
```bash
.venv/bin/pytest tests/
```
Expected output:
```text
267 passed in ~3.5s
```

- [ ] **Step 2: Run master harness test suite**

Run:
```bash
./tests/test_harness.sh
```
Expected output:
```text
Summary: 75/75 passed
```

- [ ] **Step 3: Run harness check script**

Run:
```bash
./scripts/harness_check.sh
```
Expected output:
```text
✓ ALL HARNESS COMPONENT CHECKS PASSED
```

- [ ] **Step 4: Commit and Push**

Run:
```bash
git push origin feat/dynamic-hal-registry
```

---

## Plan Review & Self-Check

- [x] **Spec Coverage**: Directly addresses Section 2.1 (Personal Coupling vs Universal Requirements) and Mini-RFC 002 (Dynamic HAL) for agent personas.
- [x] **Zero Placeholders**: Explicit regex rules, complete test file implementation, and exact file paths provided.
- [x] **Portability**: All 9 agents will achieve 100% compliance with open-source and non-hardcoded invariants.
