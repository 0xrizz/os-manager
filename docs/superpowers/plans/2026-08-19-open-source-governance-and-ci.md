# Open-Source Governance and CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish production-grade open-source community governance artifacts and configure an automated multi-OS Continuous Integration workflow matrix.

**Architecture:** Community governance implements standard GitHub guidelines, Contributor Covenant v2.1, and the MIT License. Continuous integration runs a multi-OS GitHub Actions workflow across Ubuntu and macOS runners.

**Tech Stack:** Markdown, GitHub Actions YAML, ShellCheck, Flake8, Python 3.10+, POSIX Bash 5+.

**Spec:** `docs/superpowers/specs/2026-08-19-open-source-os-manager-specification.md`

## Global Constraints

- Strict adherence to open-source repository governance standards.
- Zero sensitive credentials or personal token leaks in templates or workflows.
- 100% CI pass rate across Ubuntu 22.04, Ubuntu 24.04, and macOS-14 runners.
- Strict Title Case on markdown section headings and concise sentences under 30 words.

---

## File Structure & Responsibilities

```text
os-manager/
├── LICENSE                     # MIT License grant
├── README.md                   # Project overview, architectural topology, and quickstart
├── CONTRIBUTING.md             # Contributor guide, workflow standards, and testing rules
├── SECURITY.md                 # Vulnerability disclosure policy and safety invariants
├── CODE_OF_CONDUCT.md          # Contributor Covenant v2.1 standard
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml      # Structured bug report form
│   │   └── feature_request.yml # Structured feature proposal form
│   ├── PULL_REQUEST_TEMPLATE.md# Pull request checklist and review template
│   └── workflows/
│       └── ci.yml              # Multi-OS continuous integration pipeline
├── tests/
│   ├── test_governance.sh      # Unit test suite verifying governance artifacts & YAML syntax
│   └── test_harness.sh         # Master harness integration test suite
```

---

### Task 1: Create Unit Test Suite for Governance Artifacts (`tests/test_governance.sh`)

**Files:**
- Create: `tests/test_governance.sh`

**Interfaces:**
- Consumes: Repository files (`LICENSE`, `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.github/`).
- Produces: Executable unit test suite with 16 assertions validating document presence, required sections, and YAML syntax.

- [ ] **Step 1: Write the failing governance test suite**

Create `tests/test_governance.sh`:

```bash
#!/usr/bin/env bash
# tests/test_governance.sh - Unit tests for open-source governance and CI workflows
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
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (missing at ${file_path})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

assert_contains() {
    local test_name="$1"
    local file_path="$2"
    local pattern="$3"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if [ -f "${file_path}" ] && grep -qi "${pattern}" "${file_path}"; then
        echo "  [PASS] ${test_name}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "  [FAIL] ${test_name} (pattern '${pattern}' not found in ${file_path})"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo "=================================================="
echo "Running Open-Source Governance Unit Tests"
echo "=================================================="

# 1. Verify Core Community Governance Documents
assert_file_exists "LICENSE exists" "${WORKSPACE_ROOT}/LICENSE"
assert_contains "LICENSE is MIT" "${WORKSPACE_ROOT}/LICENSE" "MIT License"

assert_file_exists "README.md exists" "${WORKSPACE_ROOT}/README.md"
assert_contains "README has Architecture" "${WORKSPACE_ROOT}/README.md" "Architecture"
assert_contains "README has Quickstart" "${WORKSPACE_ROOT}/README.md" "Quickstart"

assert_file_exists "CONTRIBUTING.md exists" "${WORKSPACE_ROOT}/CONTRIBUTING.md"
assert_contains "CONTRIBUTING has Testing" "${WORKSPACE_ROOT}/CONTRIBUTING.md" "Testing"

assert_file_exists "SECURITY.md exists" "${WORKSPACE_ROOT}/SECURITY.md"
assert_contains "SECURITY has Disclosure" "${WORKSPACE_ROOT}/SECURITY.md" "Reporting a Vulnerability"

assert_file_exists "CODE_OF_CONDUCT.md exists" "${WORKSPACE_ROOT}/CODE_OF_CONDUCT.md"
assert_contains "CODE_OF_CONDUCT is Contributor Covenant" "${WORKSPACE_ROOT}/CODE_OF_CONDUCT.md" "Contributor Covenant"

# 2. Verify GitHub Community Templates
assert_file_exists "Bug report template exists" "${WORKSPACE_ROOT}/.github/ISSUE_TEMPLATE/bug_report.yml"
assert_file_exists "Feature request template exists" "${WORKSPACE_ROOT}/.github/ISSUE_TEMPLATE/feature_request.yml"
assert_file_exists "Pull request template exists" "${WORKSPACE_ROOT}/.github/PULL_REQUEST_TEMPLATE.md"

# 3. Verify CI Workflow YAML Configuration
assert_file_exists "CI workflow exists" "${WORKSPACE_ROOT}/.github/workflows/ci.yml"
assert_contains "CI workflow tests Ubuntu" "${WORKSPACE_ROOT}/.github/workflows/ci.yml" "ubuntu-24.04"
assert_contains "CI workflow tests macOS" "${WORKSPACE_ROOT}/.github/workflows/ci.yml" "macos-14"

# 4. Validate YAML Syntax using Python
TOTAL_TESTS=$((TOTAL_TESTS + 1))
YAML_CHECK_RC=0
python3 -c '
import yaml, glob, sys
for yml in glob.glob("'"${WORKSPACE_ROOT}"'/.github/**/*.yml", recursive=True):
    with open(yml, "r", encoding="utf-8") as f:
        yaml.safe_load(f)
' > /dev/null 2>&1 || YAML_CHECK_RC=$?

if [ "${YAML_CHECK_RC}" -eq 0 ]; then
    echo "  [PASS] All GitHub YAML files have valid syntax"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "  [FAIL] YAML syntax error detected in .github/"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

echo "=================================================="
echo "Summary: ${PASSED_TESTS}/${TOTAL_TESTS} passed"
echo "=================================================="

if [ "${FAILED_TESTS}" -gt 0 ]; then
    exit 1
fi
```

- [ ] **Step 2: Run test suite to verify failure**

Run: `chmod +x tests/test_governance.sh && ./tests/test_governance.sh`
Expected: FAIL (missing governance files).

- [ ] **Step 3: Commit initial governance test suite**

```bash
git add tests/test_governance.sh
git commit -m "test(governance): add open-source governance unit test suite"
```

---

### Task 2: Implement Core Community Governance Documents

**Files:**
- Create: `LICENSE`
- Create: `README.md`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `CODE_OF_CONDUCT.md`

**Interfaces:**
- Consumes: Project specifications in `docs/PRD.md` and `docs/superpowers/specs/2026-08-19-open-source-os-manager-specification.md`.
- Produces: Production-grade markdown documentation fulfilling open-source community standards.

- [ ] **Step 1: Create `LICENSE` (MIT)**

Create `LICENSE`:

```text
MIT License

Copyright (c) 2026 OS-Manager Maintainers

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Create `README.md`**

Create `README.md`:

```markdown
# OS-Manager

Autonomous governance harness, security control plane, and operational automation engine for Claude Code across Linux, WSL2, and macOS.

## Overview

Modern software engineering combines polyglot toolchains with autonomous artificial intelligence coding agents. Operating high-throughput developer toolchains alongside autonomous coding agents introduces distinct operational challenges: unconstrained shell command execution, virtual disk bloat, filesystem virtualization latency, and workstation drift.

`os-manager` provides a unified control plane uniting deterministic security guardrails, background telemetry, disaster recovery, and cross-platform runtime abstractions.

---

## Architectural Topology

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

## Core Features

- **4-Tier Security Guardrails**: Intercepts tool calls deterministically with `PreToolUse` lifecycle hooks. Hard-blocks destructive operations with Exit Code 2.
- **Cross-Platform Support**: Operates seamlessly across native Linux (Debian, Ubuntu, Arch, Fedora, openSUSE), WSL2 (with Windows host bridge), and macOS (Darwin).
- **Zero-Dependency Observability**: Provides Prometheus metrics exporter daemon (`scripts/metrics_exporter.py`) and monotonic hook latency tracing.
- **Desktop Alert Bridge**: Delivers notifications via Windows WinRT toast, macOS AppleScript, or Linux `notify-send`.
- **Automated Workstation Compaction**: Compacts backing virtual disk containers (`.vhdx`) when slack space exceeds configurable thresholds.
- **Dual Distribution Models**: Supports standalone Git clone installer (`./install.sh`) and Python package CLI (`osm` via `uv tool install os-manager`).

---

## Quickstart

### Option 1: Standalone Shell Installer

```bash
git clone https://github.com/0xrizz/os-manager.git ~/.os-manager
cd ~/.os-manager
./install.sh
```

### Option 2: Python Tool Installation

```bash
uv tool install os-manager
osm check
```

---

## Common Commands

- Run full test harness suite: `osm check` or `./tests/test_harness.sh`
- Inspect system diagnostics: `osm diag` or `/diag`
- Evict system and package caches: `osm clean --all` or `/clean`
- Benchmark filesystem I/O: `osm perf` or `/perf`
- Manage background timer units: `./scripts/manage_timers.sh status`

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
```

- [ ] **Step 3: Create `CONTRIBUTING.md`**

Create `CONTRIBUTING.md`:

```markdown
# Contributing to OS-Manager

Thank you for your interest in contributing to `os-manager`. This project welcomes contributions from everyone.

## Code of Conduct

All contributors are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).

## Development Workflow

1. Fork the repository on GitHub.
2. Clone your fork locally.
3. Create a descriptive feature branch:
   ```bash
   git checkout -b feat/my-new-feature
   ```
4. Follow the Test-Driven Development (TDD) discipline:
   - Write failing unit tests first.
   - Implement the minimal necessary changes.
   - Verify that all tests pass.
5. Ensure your scripts pass static analysis:
   ```bash
   shellcheck scripts/**/*.sh tests/**/*.sh
   python3 -m py_compile scripts/*.py os_manager/**/*.py
   ```
6. Verify that the master harness passes:
   ```bash
   ./tests/test_harness.sh
   ```
7. Commit your changes following Conventional Commits format (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`).
8. Open a Pull Request on GitHub.

## Coding and Style Standards

- Maintain strict `set -euo pipefail` on all shell scripts.
- Use POSIX LF line endings.
- Do not introduce external runtime dependencies for core CLI utilities.
- Follow the writing rules defined in `agent-style v0.4.2` for all markdown documentation.
```

- [ ] **Step 4: Create `SECURITY.md`**

Create `SECURITY.md`:

```markdown
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in `os-manager`, please do not open a public issue.

Report security issues directly to the maintainers via email at `security@os-manager.dev` or through private GitHub Security Advisories.

We review incoming vulnerability reports within 48 hours and release patched versions promptly.

## Security Invariants

The `os-manager` control plane enforces strict safety invariants:

1. **Root Protection**: Commands executing root obliteration (`rm -rf /`) or home directory deletion are hard-blocked.
2. **Lifecycle Safeguards**: Destructive WSL unregistration commands (`wsl --unregister`) are blocked deterministically.
3. **Container Sandboxing**: Untrusted subagent execution occurs within rootless container wrappers with read-only root filesystems.
```

- [ ] **Step 5: Create `CODE_OF_CONDUCT.md`**

Create `CODE_OF_CONDUCT.md`:

```markdown
# Contributor Covenant Code of Conduct

## Our Pledge

We as members, contributors, and leaders pledge to make participation in our
community a harassment-free experience for everyone, regardless of age, body
size, visible or invisible disability, ethnicity, sex characteristics, gender
identity and expression, level of experience, education, socio-economic status,
nationality, personal appearance, race, caste, color, religion, or sexual
identity and orientation.

We pledge to act and interact in ways that contribute to an open, welcoming,
diverse, inclusive, and healthy community.

## Our Standards

Examples of behavior that contributes to a positive environment for our
community include:

* Demonstrating empathy and kindness toward other people
* Being respectful of differing opinions, viewpoints, and experiences
* Giving and gracefully accepting constructive feedback
* Accepting responsibility and apologizing to those affected by our mistakes,
  and learning from the experience
* Focusing on what is best not just for us as individuals, but for the
  overall community

Examples of unacceptable behavior include:

* The use of sexualized language or imagery, and sexual attention or advances of
  any kind
* Trolling, insulting or derogatory comments, and personal or political attacks
* Public or private harassment
* Publishing others' private information, such as a physical or email
  address, without their explicit permission
* Other conduct which could reasonably be considered inappropriate in a
  professional setting

## Enforcement Responsibilities

Community leaders are responsible for clarifying and enforcing our standards of
acceptable behavior and will take appropriate and fair corrective action in
response to any behavior that they deem inappropriate, threatening, offensive,
or harmful.

## Scope

This Code of Conduct applies within all community spaces, and also applies when
an individual is officially representing the community in public spaces.

## Attribution

This Code of Conduct is adapted from the [Contributor Covenant][homepage],
version 2.1, available at
https://www.contributor-covenant.org/version/2/1/code_of_conduct.html.

[homepage]: https://www.contributor-covenant.org
```

- [ ] **Step 6: Run `tests/test_governance.sh` to observe partial pass**

Run: `./tests/test_governance.sh`
Expected: Passes document checks; fails on missing `.github/` templates and workflows.

- [ ] **Step 7: Commit core governance files**

```bash
git add LICENSE README.md CONTRIBUTING.md SECURITY.md CODE_OF_CONDUCT.md
git commit -m "docs(governance): add core open-source community governance documents"
```

---

### Task 3: Implement GitHub Community Issue and PR Templates

**Files:**
- Create: `.github/ISSUE_TEMPLATE/bug_report.yml`
- Create: `.github/ISSUE_TEMPLATE/feature_request.yml`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`

**Interfaces:**
- Consumes: GitHub Actions issue form specifications.
- Produces: Structured, YAML-validated issue reporting forms and pull request templates.

- [ ] **Step 1: Create `.github/ISSUE_TEMPLATE/bug_report.yml`**

Create `.github/ISSUE_TEMPLATE/bug_report.yml`:

```yaml
name: Bug Report
description: Report an issue or unexpected failure in os-manager
title: "[Bug]: "
labels: ["bug", "triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thank you for reporting a bug. Please provide clear details to help reproduce the issue.
  - type: input
    id: version
    attributes:
      label: OS-Manager Version
      description: What version of os-manager are you running? (Run `osm --version` or check git commit)
      placeholder: "1.0.0"
    validations:
      required: true
  - type: dropdown
    id: platform
    attributes:
      label: Operating Platform
      description: Select your operating environment
      options:
        - "WSL2 (Windows 11)"
        - "Linux (Debian / Ubuntu)"
        - "Linux (Arch / Fedora / openSUSE)"
        - "macOS (Darwin)"
        - "Other"
    validations:
      required: true
  - type: textarea
    id: description
    attributes:
      label: Describe the Bug
      description: A clear and concise description of what happened.
    validations:
      required: true
  - type: textarea
    id: reproduction
    attributes:
      label: Steps to Reproduce
      description: Exact commands executed leading to the error.
      placeholder: |
        1. Run 'osm clean'
        2. Inspect output
    validations:
      required: true
  - type: textarea
    id: logs
    attributes:
      label: Diagnostic Logs
      description: Relevant output from `./scripts/sys_diag.sh` or `backups/logs/`.
      render: shell
```

- [ ] **Step 2: Create `.github/ISSUE_TEMPLATE/feature_request.yml`**

Create `.github/ISSUE_TEMPLATE/feature_request.yml`:

```yaml
name: Feature Proposal
description: Suggest a new feature, platform adapter, or capability
title: "[Feature]: "
labels: ["enhancement"]
body:
  - type: markdown
    attributes:
      value: |
        Thank you for proposing an enhancement to os-manager.
  - type: textarea
    id: problem
    attributes:
      label: Problem or Use Case
      description: What problem does this feature solve?
    validations:
      required: true
  - type: textarea
    id: proposed_solution
    attributes:
      label: Proposed Solution
      description: How should this feature work?
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives Considered
      description: Any alternative approaches or workarounds considered.
```

- [ ] **Step 3: Create `.github/PULL_REQUEST_TEMPLATE.md`**

Create `.github/PULL_REQUEST_TEMPLATE.md`:

```markdown
## Description

Please provide a summary of the changes introduced in this pull request.

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Refactoring (code improvement with no functional change)
- [ ] Documentation update
- [ ] Test harness update

## Verification Checklist

- [ ] Master test harness passes locally (`./tests/test_harness.sh`)
- [ ] Shell scripts pass static analysis (`shellcheck scripts/**/*.sh tests/**/*.sh`)
- [ ] Python modules compile cleanly (`python3 -m py_compile scripts/*.py os_manager/**/*.py`)
- [ ] Writing style complies with `agent-style v0.4.2` rules
- [ ] No hardcoded user directories or credentials added
```

- [ ] **Step 4: Run `tests/test_governance.sh` to observe progress**

Run: `./tests/test_governance.sh`
Expected: Template checks pass; fails only on missing `.github/workflows/ci.yml`.

- [ ] **Step 5: Commit GitHub community templates**

```bash
git add .github/ISSUE_TEMPLATE/ .github/PULL_REQUEST_TEMPLATE.md
git commit -m "feat(community): add GitHub issue forms and pull request template"
```

---

### Task 4: Configure GitHub Actions Continuous Integration Workflow (`.github/workflows/ci.yml`)

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: GitHub Actions runner environments (`ubuntu-22.04`, `ubuntu-24.04`, `macos-14`).
- Produces: Automated multi-job CI workflow validating linters and test suites.

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

Create `.github/workflows/ci.yml`:

```yaml
name: CI Suite

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    name: Code Quality & Static Analysis
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Linting Tools
        run: |
          sudo apt update && sudo apt install -y shellcheck jq
          pip install flake8 pyyaml

      - name: ShellCheck Lint
        run: |
          shellcheck scripts/**/*.sh tests/**/*.sh install.sh

      - name: Python Syntax & Lint
        run: |
          python3 -m py_compile scripts/*.py tests/*.py os_manager/**/*.py
          flake8 scripts/ os_manager/ tests/ --max-line-length=120 --ignore=E402,W503

      - name: Validate YAML Syntax
        run: |
          python3 -c '
          import yaml, glob
          for yml in glob.glob(".github/**/*.yml", recursive=True):
              with open(yml, "r", encoding="utf-8") as f:
                  yaml.safe_load(f)
          '

  test-linux:
    name: Linux Harness Test Suite
    needs: lint
    strategy:
      matrix:
        os: [ubuntu-22.04, ubuntu-24.04]
    runs-on: ${{ matrix.os }}
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Runtime Prerequisites
        run: |
          sudo apt update && sudo apt install -y jq curl podman

      - name: Run Master Harness Test Suite
        run: |
          chmod +x tests/*.sh scripts/*.sh install.sh
          ./tests/test_harness.sh

  test-macos:
    name: macOS Harness Test Suite
    needs: lint
    runs-on: macos-14
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Runtime Prerequisites
        run: |
          brew install jq

      - name: Run Master Harness Test Suite
        run: |
          chmod +x tests/*.sh scripts/*.sh install.sh
          ./tests/test_harness.sh
```

- [ ] **Step 2: Run `tests/test_governance.sh` to verify full pass**

Run: `./tests/test_governance.sh`
Expected: PASS (All 16 governance and CI assertions pass).

- [ ] **Step 3: Commit GitHub Actions workflow**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(github): add multi-OS continuous integration workflow matrix"
```

---

### Task 5: Integrate Master Harness Assertions (`tests/test_harness.sh`)

**Files:**
- Modify: `tests/test_harness.sh:1-190`

**Interfaces:**
- Consumes: `tests/test_governance.sh`.
- Produces: Master harness suite with open-source governance validation assertions (total assertions reaching 55+).

- [ ] **Step 1: Add integration assertions to `tests/test_harness.sh`**

Append to `tests/test_harness.sh`:

```bash
echo "--- Testing Governance & CI Configuration Suite ---"
set +e
"${WORKSPACE_ROOT}/tests/test_governance.sh" > /dev/null 2>&1
assert_exit_code "test_governance.sh execution" 0 $?
set -e
```

- [ ] **Step 2: Run full test harness suite**

Run: `./tests/test_harness.sh`
Expected: PASS (All 55 assertions pass with 0 failures).

- [ ] **Step 3: Run comprehensive harness check**

Run: `./scripts/harness_check.sh`
Expected: PASS with 100% health score.

- [ ] **Step 4: Commit master harness integration**

```bash
git add tests/test_harness.sh
git commit -m "test(harness): integrate open-source governance and CI assertions"
```

---

## Plan Self-Review

### 1. Spec Coverage
- **Community Governance Artifacts**: Fully specified in Task 2 (`LICENSE`, `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`).
- **GitHub Issue and PR Templates**: Fully specified in Task 3 (`bug_report.yml`, `feature_request.yml`, `PULL_REQUEST_TEMPLATE.md`).
- **Multi-OS CI Matrix**: Fully specified in Task 4 (`.github/workflows/ci.yml` covering `lint`, `test-linux` across Ubuntu 22.04 & 24.04, and `test-macos` on macos-14).
- **Master Harness Integration**: Fully specified in Task 5 (`tests/test_harness.sh`).

### 2. Placeholder Scan
- Zero placeholders found. Every file contains complete, production-ready content without ellipsis or "TODO" notes.

### 3. Style & Syntax Consistency
- Markdown files follow standard Title Case headings and short sentences under 30 words.
- All YAML files adhere to strict GitHub Actions and issue template schemas.
