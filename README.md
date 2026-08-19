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
