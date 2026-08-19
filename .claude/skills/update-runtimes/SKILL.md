---
name: update-runtimes
description: Use when upgrading system packages, refreshing development runtimes (Node, PNPM, Bun, UV), or updating AI coding CLIs to their latest stable releases
---

# Update Runtimes Skill

Coordinates automated updates across Debian package repositories, Node/NVM toolchains, Bun runtime, Astral UV, and AI coding CLIs.

## Trigger Scenarios
- Outdated APT package lists or pending security updates on Debian WSL2
- Node/NVM toolchains, Bun runtime, or Astral UV requiring binary updates
- Updating AI coding assistant CLIs (`claude`, `wrangler`, `agy`)
- Scheduled development runtime refresh and toolchain synchronization

## Invocation
```bash
${CLAUDE_PROJECT_DIR}/scripts/update_runtimes.sh [flags]
```

## Command Options
| Option | Description |
| :--- | :--- |
| *(none)* | Coordinates full update sequence across APT, Node/PNPM, Bun, UV, and AI CLIs |
| `--check` | Dry run checking for available updates without applying |
| `--system-only` | Updates Debian system APT packages only |
| `--runtimes-only` | Updates Node, Bun, and UV toolchains only |
| `--ai-only` | Updates AI coding assistants and CLI tooling only |

## Safety Classification
- **Tier 2 (Controlled System Operation)**: Pre-authorized update coordinator modifying runtime binaries and package manager state safely.
