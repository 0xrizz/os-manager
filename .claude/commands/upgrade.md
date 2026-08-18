# /upgrade: Runtime & Toolchain Upgrade Command

Coordinates automated updates across Debian package repositories, Node/NVM toolchains, Bun runtime, Astral UV, and AI coding CLIs.

## Invocation
```bash
/home/rizz/dev/os-manager/scripts/update_runtimes.sh "$@"
```

## Description
Maintains parity and security across development toolchains:
- Refreshes APT package lists and upgrades installed packages (`apt-get update && apt-get upgrade -y`)
- Upgrades global PNPM and npm packages
- Updates Bun runtime binary (`bun upgrade`)
- Self-updates Astral UV (`uv self update`)
- Updates installed AI coding CLIs (`claude`, `agy` Antigravity CLI)
- Verifies post-upgrade binary availability and versions in `$PATH`

## Flags & Arguments
- `--check`: Dry run checking for available updates without applying
- `--system-only`: Updates Debian system APT packages only
- `--runtimes-only`: Updates Node, Bun, and UV toolchains only
- `--ai-only`: Updates AI coding assistants and CLI tooling only
