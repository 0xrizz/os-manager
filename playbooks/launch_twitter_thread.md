# X / Twitter Technical Launch Thread

## Post 1 (Hook & Media)
What happens when you let an autonomous AI coding agent run for 6 hours? Without guardrails: catastrophic host churn and virtual disk bloat.

Introducing `os-manager`: The open-source safety harness and control plane for Claude Code. 🛡️⚡

[Attach demo.gif]

## Post 2 (Dilemma)
The problem: Developers face two extremes with AI coding agents:
1. Friction-heavy permission prompts every 30 seconds
2. Unconstrained execution that risks accidental `rm -rf` or host corruption

`os-manager` introduces a deterministic 4-tier security matrix to bridge this gap.

## Post 3 (Auto-Sandbox Architecture)
Instead of failing with red error walls, `os-manager` reroutes risky operations into disposable, rootless Podman containers.

Host sabotage is hard-vetoed. Risky operations run isolated. Your agent workflow never breaks.

## Post 4 (Workstation Performance & Hygiene)
Beyond safety, `os-manager` keeps your dev machine lean:
• Automated WSL2 VHDX compaction (>10GB reclaimed)
• Zero 9P virtualization lag on ext4
• Built-in Prometheus metrics daemon (`:9100`)
• Nanosecond hook latency tracing (<50ms P99)

## Post 5 (Get Started & Open Source)
Try `os-manager` in 10 seconds:

```bash
curl -fsSL https://raw.githubusercontent.com/0xrizz/os-manager/main/install.sh | bash
```

100% open source under MIT. 55/55 tests passing.
⭐ Star on GitHub: https://github.com/0xrizz/os-manager
