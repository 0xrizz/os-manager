# Show HN Launch Playbook

## Submission Details

- **Title**: Show HN: os-manager - Open-source safety harness and sandbox for Claude Code
- **URL**: https://github.com/0xrizz/os-manager

## First Comment (Maker Comment)

Hey HN,

Running autonomous AI coding loops (like Claude Code) on developer machines creates a dilemma. Developers must either click constant permission prompts, or grant broad execution rights and risk filesystem churn.

`os-manager` is a lightweight governance harness and control plane that wraps Claude Code with deterministic POSIX lifecycle hooks:

1. **4-Tier Security Matrix**: Intercepts tool calls deterministically. Host-level sabotage (such as `/mnt/c/Windows`, `/etc/shadow`) is hard-blocked with Exit Code 2.
2. **Auto-Sandbox Fallback**: Risky commands (`rm -rf ./temp`, heavy package purges) automatically reroute into disposable rootless Podman containers, keeping the agent loop running without host blast radius.
3. **Workstation Hygiene**: Reclaims VHDX disk space on WSL2, enforces native ext4 storage boundaries, and exports Prometheus metrics (`:9100`).
4. **Zero-Secret Distribution**: Published to PyPI via OIDC Trusted Publishing with automated SHA256 checksum generation.

Quickstart:
```bash
curl -fsSL https://raw.githubusercontent.com/0xrizz/os-manager/main/install.sh | bash
```

Everything is open source under MIT, with a 55-assertion test suite running on Linux, WSL2, and macOS.

I welcome feedback on additional guardrails or workstation automation profiles to add.
