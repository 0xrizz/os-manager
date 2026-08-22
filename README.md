```text
 ██████╗ ███████╗      ███╗   ███╗ █████╗ ███╗   ██╗ █████╗  ██████╗ ███████╗██████╗ 
██╔═══██╗██╔════╝      ████╗ ████║██╔══██╗████╗  ██║██╔══██╗██╔════╝ ██╔════╝██╔══██╗
██║   ██║███████╗█████╗██╔████╔██║███████║██╔██╗ ██║███████║██║  ███╗█████╗  ██████╔╝
██║   ██║╚════██║╚════╝██║╚██╔╝██║██╔══██║██║╚██╗██║██╔══██║██║   ██║██╔══╝  ██╔══██╗
╚██████╔╝███████║      ██║ ╚═╝ ██║██║  ██║██║ ╚████║██║  ██║╚██████╔╝███████╗██║  ██║
 ╚═════╝ ╚══════╝      ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
```

# os-manager — Autonomous Claude Code Harness, Security Matrix & WSL2 Automation Suite

<p align="center">
  <a href="https://github.com/0xrizz/os-manager/actions"><img src="https://img.shields.io/github/actions/workflow/status/0xrizz/os-manager/ci.yml?branch=main&label=CI&logo=github" alt="CI Status"></a>
  <a href="https://pypi.org/project/0xrizz-os-manager/"><img src="https://img.shields.io/pypi/v/0xrizz-os-manager?color=blue&logo=pypi" alt="PyPI Version"></a>
  <a href="https://github.com/0xrizz/os-manager/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT"></a>
  <a href="https://github.com/0xrizz/os-manager"><img src="https://img.shields.io/badge/tests-148%2F148%20passing-brightgreen" alt="Tests"></a>
</p>

<p align="center">
  <strong>Run Claude Code autonomously without fear of host destruction.</strong><br>
  Open-source governance harness, 4-tier security matrix, auto-sandbox fallback, and background telemetry engine across Linux, WSL2, and macOS by <a href="https://github.com/0xrizz">@0xrizz</a>.
</p>

---

## ⚡ Quickstart (10 Seconds)

Install and configure hooks, guardrails, and slash commands in a single command:

```bash
curl -fsSL https://raw.githubusercontent.com/0xrizz/os-manager/main/install.sh | bash
```

Or install via Python toolchain:

```bash
uv tool install 0xrizz-os-manager
osm check
```

```text
┌── [osm] System & Harness Status ─────────────────────────────────────────┐
│ • Platform      : Debian 13 (Trixie) WSL2 | Linux 6.18.x                 │
│ • Security      : Tier 0-3 Guard Active (Exit 2 on host violation)       │
│ • Virtualization: Rootless Podman Sandbox Fallback Ready                 │
│ • Observability : Prometheus Exporter (:9100) + Monotonic Tracing        │
│ • Test Engine   : 148/148 Assertions Passing [100% OK]                   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Core Features

- **4-Tier Security Matrix**: Deterministically blocks host sabotage (`/mnt/c/Windows`, `/etc/shadow`) with hard zero-trust vetoes (Exit Code 2).
- **Auto-Sandbox Fallback**: Seamlessly reroutes risky operations (`rm -rf`, heavy purges) into rootless Podman containers without aborting turns.
- **Workstation Performance**: Automated VHDX compaction, zero 9P latency enforcement on ext4, and fast cache cleanup.
- **Background Observability**: Built-in Prometheus metrics exporter (`127.0.0.1:9100`) and nanosecond hook latency tracing.
- **Multi-Agent SSOT Bridge**: Zero-copy relative symlinks synchronizing skills across Claude Code, Universal Agent, and Google Antigravity.
- **Host Security ID (HSI) Hardening**: Hardware security posture audit and remediation engine (zRAM swap encryption, s2idle sleep, DBX revocation).

---

### 🛡️ Host Security ID (HSI) Hardening Engine

Audit and harden hardware security postures against firmware, cold-boot, and unencrypted swap vulnerabilities:

```bash
osm hsi audit          # Audit HSI security posture (sleep mode, swap encryption, DBX)
osm hsi audit --json   # Telemetry output in JSON format
osm hsi apply --dry-run # Simulate hardening steps
sudo osm hsi apply     # Apply automated zRAM swap, s2idle sleep, and DBX updates
```

---

## 🏛️ Harness Architecture

```text
╔════════════════════════════════════════════════════════════════════════════════════╗
║═════════════════════════ OS-MANAGER CONTROL PLANE MATRIX ══════════════════════════║
╠════════════════════════════════════════════════════════════════════════════════════╣
║                                                                                    ║
║  ┌─ [01] GOVERNANCE & CORE HARNESS ────────────────────────────────────────────┐   ║
║  │  • .claude/settings.json       • .claude/rules/ (Safety & WSL Boundaries)   │   ║
║  │  • CLAUDE.md Governance        • Zero 9P Latency Native EXT4 Enforcement    │   ║
║  └─────────────────────────────────────┬───────────────────────────────────────┘   ║
║                                        │ [DISPATCH]                                ║
║         ┌──────────────────────────────┼──────────────────────────────┐            ║
║         ▼                              ▼                              ▼            ║
║  ┌──────────────┐              ┌──────────────┐              ┌──────────────┐      ║
║  │  LIFECYCLE   │              │   COMMANDS   │              │ MULTI-AGENT  │      ║
║  │    HOOKS     │              │    SUITE     │              │    BRIDGE    │      ║
║  ├──────────────┤              ├──────────────┤              ├──────────────┤      ║
║  │•SessionStart │              │• /diag       │              │• Claude Code │      ║
║  │•PreToolGuard │              │• /clean      │              │• UniversalAgt│      ║
║  │•PostToolLint │              │• /upgrade    │              │• Antigravity │      ║
║  │•PostFailure  │              │• /snapshot   │              │• Message Bus │      ║
║  │•PreCompact   │              │• /pair       │              │  (JSON-RPC)  │      ║
║  └──────┬───────┘              └──────────────┘              └──────┬───────┘      ║
║         │                                                           │              ║
║         ▼                                                           ▼              ║
║  ┌─────────────────────────────────────┐   ┌────────────────────────────────┐      ║
║  │ 4-TIER SECURITY MATRIX (HARD VETO 2)│   │ROOTLESS PODMAN SANDBOX FALLBACK│      ║
║  │[T0: ReadOnly] [T1: Local] [T2: Safe]│<─>│Isolated Execution for Risky Cmd│      ║
║  │[T3: Invariant Block / Root Guard]   │   │(Zero Host Sabotage Guaranteed) │      ║
║  └─────────────────────────────────────┘   └────────────────────────────────┘      ║
║                                                                                    ║
╚════════════════════════════════════════════════════════════════════════════════════╝
```

---

## 💻 Custom Slash Commands

- `/diag`: Compact Unicode health dashboard card and system status.
- `/clean`: Safe space reclamation across APT, UV, PNPM, Bun, and `/tmp`.
- `/upgrade`: Coordinated toolchain and runtime updates.
- `/snapshot`: Disaster recovery point-in-time distro backups.
- `/pair`: Spawns paired multi-agent Tmux workspace (Claude Code + Antigravity).

---

## 👤 Author & Maintainer

Maintained and developed by **[0xrizz](https://github.com/0xrizz)**.

- **Repository**: [https://github.com/0xrizz/os-manager](https://github.com/0xrizz/os-manager)
- **Issues & Discussions**: [https://github.com/0xrizz/os-manager/issues](https://github.com/0xrizz/os-manager/issues)

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
