# Open-Source Transformation Design Specification for OS-Manager

> **STATUS: SUPERSEDED**
> **Superseded by:** `docs/superpowers/specs/2026-08-24-open-source-transformation-roadmap-design.md` on 2026-08-24.
> **Reason:** Initial distribution baseline upgraded to include Shell AST-based Zero-Trust security guards, dynamic Hardware Abstraction Layer (HAL), native Model Context Protocol (MCP) server engine, and multi-agent SQLite event ledger.

## 1. Executive Summary

This document specifies the open-source transformation design for the `os-manager` platform. `os-manager` is an autonomous governance harness and system control plane built for Claude Code. The transformation transitions the repository from a single-machine development environment into a production-grade, community-ready open-source framework.

The design establishes three primary deliverables:

1. **Dual-Tier Distribution Architecture**: Users install the platform via Git clone with `./install.sh`, or via a Python package (`osm` CLI via `uv tool install os-manager`).
2. **Universal Cross-Platform Abstraction**: The platform expands beyond Debian WSL2 to support Linux distributions (Debian, Ubuntu, Arch, Fedora, openSUSE), WSL2 host integrations, and macOS (Darwin) environments.
3. **Open-Source Governance and Quality Assurance**: The repository implements the MIT License, public issue templates, contribution guides, security policies, and continuous integration across Linux and macOS GitHub Actions runners.

---

## 2. Architecture and Platform Abstraction

### 2.1 System Topology

The `os-manager` architecture decouples command-line user interaction, platform-specific operating system adapters, and the Claude Code governance runtime.

```text
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                      USER INVOCATION INTERFACE                                  │
 │         Dual Distribution: Git Clone + ./install.sh   OR   `uv tool install os-manager`        │
 └────────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                  │
                                    ┌─────────────▼─────────────┐
                                    │    `osm` Python CLI Entry │
                                    │ (init, check, diag, clean)│
                                    └─────────────┬─────────────┘
                                                  │
 ┌────────────────────────────────────────────────▼────────────────────────────────────────────────┐
 │ PLATFORM ABSTRACTION ENGINE (`scripts/lib/platform.sh` & `os_manager.platform`)                 │
 │ • OS Kernel Detection (Linux native, WSL2 on Windows, macOS Darwin)                             │
 │ • Package Manager Adapter (`apt`, `dnf`, `pacman`, `zypper`, `brew`, `pkg`)                     │
 │ • Service Supervision Adapter (systemd user units, macOS launchd agents)                       │
 │ • Host Notification Adapter (WSL2 WinRT bridge, macOS osascript, Linux notify-send)             │
 └────────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                  │
 ┌────────────────────────────────────────────────▼────────────────────────────────────────────────┐
 │ CLAUDE CODE HARNESS & GOVERNANCE CORE (`.claude/`)                                              │
 │ • Lifecycle Hooks Engine (`SessionStart`, `PreToolUse`, `PostToolUse`, `SessionEnd`, etc.)      │
 │ • 4-Tier Security Matrix Guardrails (Deterministic bash AST & regex checks)                     │
 │ • Zero-Dependency Prometheus Metrics Exporter & Unix-Socket Inter-Agent Bus                     │
 │ • Automated Workstation Maintenance & Slash Commands (`/diag`, `/clean`, `/perf`, etc.)        │
 └─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Platform Abstraction Layer

The platform abstraction layer resides in `scripts/lib/platform.sh` for shell routines and `os_manager/platform/` for Python modules.

#### 2.2.1 Operating System Detection

The detection routine determines the host environment through system attributes:

- **Linux Native**: Inspects `/etc/os-release` to identify the distribution ID (`ID` and `ID_LIKE`). Linux package operations map to `apt`, `dnf`, `pacman`, or `zypper`.
- **WSL2 (Linux on Windows)**: Inspects `/proc/version` and `/proc/sys/kernel/osrelease` for Microsoft kernel identifiers. When detected, the platform activates WSL2-specific integrations: host toast notifications (`scripts/notify_host.sh`), VHDX disk compaction (`scripts/compact_host_disk.sh`), and PowerShell recovery provisioning (`scripts/bootstrap_wsl.ps1`).
- **macOS (Darwin)**: Checks `uname -s` for `Darwin`. macOS operations map package tasks to Homebrew (`brew`), desktop alerts to AppleScript (`osascript`), and daemons to Launchd property lists (`~/Library/LaunchAgents/`).

#### 2.2.2 Path Parametrization and Multi-User Portability

The platform removes hardcoded personal directory paths. All path references resolve through environment variables with fallback defaults:

- Root directory: `${OSM_ROOT:-$HOME/.os-manager}` or `${CLAUDE_PROJECT_DIR}` when operating inside a project.
- Backup storage: `${OSM_BACKUP_DIR:-$HOME/.local/share/os-manager/backups}`.
- Telemetry logs: `${OSM_LOG_DIR:-$HOME/.local/state/os-manager/logs}`.
- IPC socket directory: `${OSM_RUN_DIR:-/tmp/os-manager-${UID}}`.

---

## 3. Dual-Tier Packaging and Distribution

### 3.1 Git Repository and Shell Installer (`./install.sh`)

The shell installer provisions the platform on systems without Python packaging tools.

#### Execution Flags

- `./install.sh`: Standard local installation into `~/.os-manager`.
- `./install.sh --global`: Configures global Claude Code hooks in `~/.claude/settings.json`.
- `./install.sh --project <dir>`: Scaffolds project-specific Claude Code governance files into the target directory.
- `./install.sh --uninstall`: Removes configuration symlinks and daemon service definitions cleanly.

#### Installer Operations

1. Detects operating platform and verifies core dependencies (`git`, `bash`, `jq`, `python3`).
2. Creates the directory tree under `~/.local/share/os-manager/` and `~/.local/state/os-manager/`.
3. Symlinks the executable launcher into `~/.local/bin/osm`.
4. Copies template configuration files while preserving existing user modifications.
5. Configures platform service units (systemd user services on Linux; Launchd property lists on macOS).

### 3.2 Python Package Distribution (`os-manager`)

The Python package provides a typed CLI interface built with standard `pyproject.toml` configuration.

#### Package Metadata

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "os-manager"
version = "1.0.0"
description = "Autonomous governance harness and control plane for Claude Code"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.10"
authors = [{ name = "OS-Manager Maintainers" }]
classifiers = [
    "Development Status :: 5 - Production/Stable",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: POSIX :: Linux",
    "Operating System :: MacOS :: MacOS X",
    "Topic :: Software Development :: Quality Assurance",
]
dependencies = []

[project.scripts]
osm = "os_manager.cli:main"
```

#### CLI Command Suite (`osm`)

- `osm init [--global|--project <dir>]`: Initializes Claude Code harness configuration and hook definitions.
- `osm check [--json]`: Executes the complete test harness suite (50+ assertions) and validates environment health.
- `osm diag [--json]`: Gathers real-time CPU, RAM, storage, and platform telemetry.
- `osm clean [--dry-run|--all]`: Reclaims cache storage across supported package managers and temporary directories.
- `osm perf [--quick|--json]`: Benchmarks disk I/O and memory throughput.
- `osm service [status|start|stop|restart]`: Controls background telemetry daemons (Prometheus exporter, Inter-Agent Bus).

---

## 4. Claude Code Specialization and Security Governance

### 4.1 Lifecycle Hooks Engine

The governance layer runs deterministically during Claude Code execution sessions:

1. **`SessionStart` (`scripts/hooks/session_preflight.sh`)**: Validates runtime prerequisites, checks memory headroom (minimum 300MB), verifies background daemon status, and initializes audit logging.
2. **`PreToolUse` (`scripts/hooks/pre_tool_guard.sh`)**: Intercepts every `Bash`, `Edit`, and `Write` invocation. Evaluates commands against the 4-Tier Security Matrix, returning Exit Code 2 on invariant violations.
3. **`PostToolUse` (`scripts/hooks/post_tool_lint.sh`)**: Lints modified scripts (`bash -n`, `shellcheck`, `jq empty`, `python3 -m py_compile`), exiting with code 2 on syntax failures to prompt automated model repair.
4. **`PostToolUseFailure` (`scripts/hooks/post_tool_failure.sh`)**: Captures failed tool calls into structured telemetry logs.
5. **`PreCompact` (`scripts/hooks/pre_compact_state.sh`)**: Preserves working tree state and environment status before context truncation.
6. **`SessionEnd` (`scripts/hooks/session_cleanup.sh`)**: Removes temporary test directories and finalizes session audit logs.

### 4.2 Cross-Platform 4-Tier Security Matrix

The security matrix enforces safety invariants across Linux, WSL2, and macOS:

| Tier | Policy | Exit Code | Scope and Allowed Actions |
| :--- | :--- | :--- | :--- |
| **Tier 0** | Autonomous Read-Only | Exit Code 0 | Non-mutating queries: `git status`, `df`, `free`, `ps`, `uptime`, `uname`, `Read`, `Grep`, `Glob`. |
| **Tier 1** | Workspace Contained | Exit Code 0 | Writes and edits within `${CLAUDE_PROJECT_DIR}`, subject to post-tool syntax gates. |
| **Tier 2** | Controlled Operations | Exit Code 0 | Authorized automation tools: `scripts/*.sh`, `scripts/*.py`, and `osm` subcommands. |
| **Tier 3** | Invariant Violations | Exit Code 2 | Hard blocked destructive patterns: root/home obliteration (`rm -rf /`, `rm -rf ~`), wildcard package deletion (`apt purge *`, `pacman -Rcs *`, `brew uninstall --force *`), raw disk writes (`dd`, `mkfs`), and host operating system directories (`/mnt/c/Windows`, `/System`, `/Library`). |

---

## 5. Open-Source Governance, Repository Sanitization and CI/CD

### 5.1 Repository Sanitization Requirements

Before public release, the repository must meet strict privacy and portability requirements:

1. **Path Neutrality**: Verify zero references to personal usernames or fixed paths across all tracked files.
2. **Clean Dotfiles Templates**: Convert backed-up dotfiles in `backups/dotfiles/` into sanitized sample templates (`.bashrc.example`, `.tmux.conf.example`, `.gitconfig.example`).
3. **Git History Inspection**: Confirm no API tokens, SSH keys, or private endpoints exist within commit history.

### 5.2 Community and Governance Documents

The repository provides standard open-source documentation:

- **`LICENSE`**: MIT License.
- **`README.md`**: Project overview, architectural diagrams, quick-start guide, and feature summary.
- **`CONTRIBUTING.md`**: Contribution workflow, code formatting standards, and test verification requirements.
- **`SECURITY.md`**: Vulnerability disclosure instructions and security matrix boundaries.
- **`CODE_OF_CONDUCT.md`**: Contributor Covenant v2.1.
- **`.github/ISSUE_TEMPLATE/`**: Issue templates for bug reports, feature proposals, and platform compatibility reports.
- **`.github/PULL_REQUEST_TEMPLATE.md`**: Standard PR checklist including test verification and style compliance.

### 5.3 Continuous Integration Matrix (`.github/workflows/ci.yml`)

The automated CI workflow executes on every pull request and push to the default branch:

```yaml
name: CI Suite

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: ShellCheck Lint
        run: shellcheck scripts/**/*.sh tests/**/*.sh
      - name: Python Syntax & Lint
        run: |
          python3 -m py_compile scripts/*.py
          flake8 scripts/ os_manager/ tests/

  test-linux:
    needs: lint
    strategy:
      matrix:
        os: [ubuntu-22.04, ubuntu-24.04]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - name: Run Master Harness Test Suite
        run: ./tests/test_harness.sh

  test-macos:
    needs: lint
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4
      - name: Run Platform Tests on macOS
        run: ./tests/test_harness.sh
```

---

## 6. Implementation Plan and Milestones

1. **Milestone 1: Repository Sanitization and Platform Abstraction Layer**
   - Create `scripts/lib/platform.sh` supporting Linux, WSL2, and macOS.
   - Parametrize all scripts to use `${OSM_ROOT}` and dynamic environment paths.
   - Convert hardcoded dotfiles to clean templates.
2. **Milestone 2: Dual-Tier Packaging and `osm` CLI Development**
   - Build `./install.sh` supporting `--global`, `--project`, and `--uninstall`.
   - Implement `pyproject.toml` and Python CLI package `os_manager/`.
   - Implement `osm init`, `osm check`, `osm diag`, and `osm clean`.
3. **Milestone 3: Open-Source Documentation and Governance Files**
   - Author `LICENSE` (MIT), `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, and `CODE_OF_CONDUCT.md`.
   - Add GitHub issue and pull request templates.
4. **Milestone 4: Multi-Platform Test Suite and CI Workflow**
   - Expand `tests/test_harness.sh` to validate Linux and macOS environments.
   - Configure `.github/workflows/ci.yml` and `.github/workflows/release.yml`.
   - Run end-to-end self-check and verification suite.
