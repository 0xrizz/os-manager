# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment and Architecture Overview

`os-manager` is an autonomous AI governance harness, workstation optimizer, and multi-agent control plane for developer environments across Debian 13 (Trixie) Bare-Metal, WSL2 on Windows 11, Linux (Ubuntu/Arch/Fedora), and macOS.

- **OS / Platform**: Debian GNU/Linux 13 (Trixie) 64-bit with Linux Kernel 6.12+ (Bare Metal) & WSL2
- **Filesystem Domain**:
  - `/` (Native ext4 Linux root): Primary high-throughput domain for git repositories, virtual environments, and builds. Avoid NTFS 9P mounts for daily dev work.
  - `/mnt/data/` (Bare Metal Persistent Storage / Drive D: on WSL2): Dedicated persistent user storage. Must NEVER be formatted or wiped.
  - `/mnt/c/` (Windows Host C:): Read-only host inspection. Direct writes to Windows system directories are strictly blocked by AST security gates.
- **Core Technology Stack**: Python 3.11+ (Standard Library `asyncio`, `dataclasses`, `argparse`, `json`, `pathlib`), Bash 5+, Bubblewrap (`bwrap`), Podman, Pytest.

---

## ⚠️ CRITICAL OPERATIONAL INVARIANTS

### 1. Non-Interactive Sudo & Terminal Execution (Zero-Stall Standard)

**Failure Mode**: Claude Code tool executions (`Bash`) run in non-interactive subshells without a TTY. Bare `sudo <cmd>` hangs waiting indefinitely on stdin or crashes immediately with `sudo: a terminal is required to read the password`.

- **Strict Rule**: NEVER execute bare interactive `sudo <command>`.
- **Primary Method (Recommended)**: Use the repository wrapper script [`scripts/sudo_exec.sh`](file:///home/rizz/dev/os-manager/scripts/sudo_exec.sh):
  ```bash
  ./scripts/sudo_exec.sh <command> [args...]
  ```
- **Secondary Method (Direct Inline Pipe)**:
  ```bash
  grep -E '^SUDO_PASSWORD=' "${CLAUDE_PROJECT_DIR:-.}/.env" | cut -d '=' -f2- | sudo -S <command>
  ```
- **Zero Password Leakage**: NEVER echo, print, or log `.env` contents or the raw password to stdout, stderr, reports, or transcripts.

```bash
# ❌ FORBIDDEN (Hangs agent session):
sudo apt-get update
sudo systemctl restart NetworkManager
sudo sysctl -p

# ✅ REQUIRED (Non-interactive execution):
./scripts/sudo_exec.sh apt-get update
./scripts/sudo_exec.sh systemctl restart NetworkManager
./scripts/sudo_exec.sh sysctl -p
```

#### Privileged Operation Recipes
| Operation | Command |
| :--- | :--- |
| **Package Management** | `./scripts/sudo_exec.sh apt-get update && ./scripts/sudo_exec.sh apt-get install -y <pkg>` |
| **Service Control** | `./scripts/sudo_exec.sh systemctl daemon-reload && ./scripts/sudo_exec.sh systemctl restart <service>` |
| **Sysctl Kernel Tuning** | `./scripts/sudo_exec.sh sysctl -w <key>=<val>` or `./scripts/sudo_exec.sh sysctl -p <file>` |
| **System File Writes** | `./scripts/sudo_exec.sh install -m 644 <src> /etc/<dest>` or `./scripts/sudo_exec.sh cp <src> <dest>` |
| **Hardware / DMI Access** | `./scripts/sudo_exec.sh dmidecode -s system-product-name` |

### 2. Non-Interactive Windows Binary Execution in WSL (`stdin` Closure)
- When invoking Windows PE binaries (`powershell.exe`, `cmd.exe`, `chkdsk.exe`), always close `stdin` via `< /dev/null` to prevent indefinite hangs.
  ```bash
  /mnt/c/Windows/System32/cmd.exe /c "dir" < /dev/null
  ```

### 3. Reactive Wakeup & Strict Ban on Polling Loops
- Never construct tight polling loops (`sleep`, repetitive `status` checks).
- Launch background tasks with sufficient async wait time and rely on reactive event notifications.

---

## 4-Tier Security Matrix & Zero-Trust Governance

Lifecycle hooks in `scripts/hooks/` and `os_manager/security/ast_guard.py` enforce strict execution tiers:

1. **Tier 0 (Autonomous Read-Only - Exit 0)**: Non-mutating inspections (`git status`, `df`, `ps`, `uptime`, `osm diag`).
2. **Tier 1 (Workspace Contained - Exit 0)**: File modifications strictly bounded within `${CLAUDE_PROJECT_DIR}/`, validated post-tool via `bash -n`, `python3 -m py_compile`, and `jq empty`.
3. **Tier 2 (Controlled Operations - Exit 0)**: Whitelisted scripts (`scripts/*.sh`, `osm` CLI commands) run pre-authorized.
4. **Tier 3 (Strict Invariants - Hard Block with Exit 2)**:
   - **Interactive Sudo**: Bare `sudo <cmd>` without `-S` or `sudo_exec.sh` is caught and blocked before hanging.
   - **Root / Home obliteration**: `rm -rf /`, `rm -rf ~`, `rm -rf $HOME`.
   - **WSL instance lifecycle destruction**: `wsl --unregister`, `wsl.exe --shutdown`.
   - **Package manager wildcard purges**: `apt purge *`, `pacman -Rcs *`.
   - **Privileged container escapes**: `podman run --privileged`, `docker run --privileged`.
   - **Raw disk partitioning / formatting**: `mkfs.*`, `fdisk`, `dd if=... of=/dev/sd*`.
   - **Protected path writes**: Modifying `/mnt/c/Windows`, `/mnt/data/`, `/etc/shadow`, `/boot/`, `/dev/`.

---

## Common Development and Operational Commands

### Testing and Validation
- Run master harness test suite (83+ assertions): `./tests/test_harness.sh`
- Run complete Pytest test suite: `.venv/bin/pytest tests/`
- Run Python unittest discovery: `.venv/bin/python -m unittest discover -s tests -p "test_*.py"`
- Run individual module test suites:
  - Sudo execution & guardrail suite: `.venv/bin/pytest tests/security/test_sudo_execution.py`
  - Multi-Agent State Ledger suite: `.venv/bin/pytest tests/ledger/`
  - Multi-Platform Packaging suite: `.venv/bin/pytest tests/packaging/`
  - MCP Protocol & Server suite: `.venv/bin/pytest tests/mcp/`
  - MCP End-to-End Stdio integration: `python3 -m unittest tests/integration/test_mcp_e2e.py`
  - Dynamic HAL & Vendor Driver suite: `.venv/bin/pytest tests/platform/`
  - Shell AST semantic parser & policy gate: `python3 -m unittest tests/security/test_ast_guard.py`
  - Declarative config engine tests: `python3 -m unittest tests/config/test_loader.py`
  - PreToolUse security hook integration: `python3 -m unittest tests/integration/test_pre_tool_guard.py`
  - Bubblewrap rootless sandbox tests: `./tests/security/test_sandbox_bwrap.sh`
  - AI Gateway & Headroom control tests: `.venv/bin/pytest tests/test_ai_*.py`
  - CLI routing unit tests: `python3 -m unittest tests/test_cli.py`
- Run full harness self-check and symlink validation: `./scripts/harness_check.sh`
- Audit Markdown prose against style rules: `for f in <file.md>; do agent-style review --audit-only "$f"; done`
- Sync multi-agent skills to Universal Agent and Antigravity: `./scripts/sync_agent_skills.sh`
- Standalone installer & scaffolding: `./install.sh [--global|--project <dir>|--uninstall|--dry-run]`

### Core CLI Commands (`osm`)
- `osm mcp serve`: Launch asynchronous JSON-RPC 2.0 stdio MCP server daemon
- `osm mcp install [--client all|claude|cursor|antigravity]`: Auto-configure MCP client settings
- `osm mcp tools`: Inspect available MCP tool declarations
- `osm check [--json]`: Run master harness test suite
- `osm diag [--json]`: Gather real-time system, platform, and DMI diagnostics
- `osm tune [status|apply|revert]`: Tune CPU governor, I/O schedulers, memory, and platform profiles
- `osm hsi [audit|apply [--dry-run]]`: Host Security ID hardware & firmware hardening
- `osm ai [status|start|stop|restart|configure]`: Unified AI gateway (Headroom & 9Router)
- `osm clean [--dry-run|--all]`: Evict package manager caches and temp files
- `osm perf`: Empirical benchmarks for storage I/O, memory, and CPU
- `osm upgrade`: Debian 13 (Trixie) upgrade coordination engine
- `osm init [--global|--project <dir>]`: Initialize Claude Code harness and hook configurations

---

## Repository Structure & Module Architecture

```text
os-manager/
├── .claude/
│   ├── agents/                  # Custom subagents (security-auditor, system-operator, etc.)
│   ├── commands/                # Custom slash commands (/diag, /clean, /perf, /snapshot, etc.)
│   ├── rules/                   # Modular prompt rules (sudo-execution, wsl-boundaries, safety-tiers)
│   ├── skills/                  # Master SSOT skill definitions
│   └── settings.json            # Master harness configuration (permissions, hooks, env)
├── os_manager/                  # Core Python package
│   ├── cli.py                   # Main CLI argument parser and routing dispatcher
│   ├── commands/                # Subcommand controllers (mcp, ai, tune, hsi, diag, clean, etc.)
│   ├── config/                  # Declarative configuration engine (.osm.toml loader & schema)
│   ├── mcp/                     # Native Model Context Protocol (MCP) server & client config
│   │   ├── protocol.py          # JSON-RPC 2.0 framing and error models
│   │   ├── tools.py             # Tool declarations (osm_safe_exec, osm_system_health, osm_tune)
│   │   ├── server.py            # Async stdio server daemon & message router
│   │   └── client_config.py     # Multi-client idempotent config injector
│   ├── platform/                # Dynamic Hardware Abstraction Layer (HAL)
│   │   ├── detector.py          # OS / Distro / Architecture detector
│   │   └── hal/                 # Vendor drivers (Lenovo, Asus, Dell, Apple, Generic Linux, ThinkPad)
│   └── security/                # Zero-trust security engine
│       └── ast_guard.py         # Shell AST semantic analysis & 4-tier policy gate
├── scripts/
│   ├── hooks/                   # Lifecycle hooks (SessionStart, PreToolUse, PostToolUse, etc.)
│   │   └── lib/trace_helper.sh  # Nanosecond hook execution monotonic tracing library
│   ├── sudo_exec.sh             # Hardened non-interactive sudo execution wrapper
│   ├── sandbox_bwrap.sh         # Bubblewrap rootless container jail
│   ├── sys_diag.sh              # System diagnostic engine
│   └── sync_agent_skills.sh     # Multi-agent SSOT symlink sync
├── tests/                       # Unit, integration, and security test suites
│   ├── config/                  # Config loader tests
│   ├── integration/             # PreToolUse guard & MCP stdio E2E tests
│   ├── mcp/                     # MCP protocol, tools, server, and client installer tests
│   ├── platform/                # HAL and vendor driver tests
│   ├── security/                # AST guard, sudo execution, and Bubblewrap sandbox tests
│   └── test_harness.sh          # Master test harness runner
└── CLAUDE.md                    # Project guidance and governance rules
```

---

## Multi-Agent Symlink Bridge & SSOT

- `.claude/skills/` is the Single Source of Truth (SSOT) for workspace-scoped skills.
- Project-specific skills remain strictly isolated within the repository workspace.
- Global promotion can be explicitly performed via `./scripts/sync_agent_skills.sh --global` if desired.
