# OS-Manager

Autonomous governance harness, security control plane, and operational automation engine for Claude Code across Linux, WSL2, and macOS.

## Overview

Modern software engineering combines polyglot toolchains with autonomous artificial intelligence coding agents. Operating high-throughput developer toolchains alongside autonomous coding agents introduces distinct operational challenges: unconstrained shell command execution, virtual disk bloat, filesystem virtualization latency, and workstation drift.

`os-manager` provides a unified control plane uniting deterministic security guardrails, background telemetry, disaster recovery, and cross-platform runtime abstractions.

---

## Architecture and Topology

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
