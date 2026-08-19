---
name: harness-check
description: Use when verifying Claude Code harness integrity, running the security hook test suite, validating multi-agent skill symlinks, or checking settings.json syntax
---

# Harness Check Skill

End-to-end self-diagnostic verification engine for the Claude Code agent harness, security hooks, multi-agent symlinks, and configuration validity.

## Trigger Scenarios
- Verifying harness integrity after modifying scripts, lifecycle hooks, or configuration
- Validating deterministic security guardrails and pre/post tool execution filters
- Checking multi-agent skill symlink synchronization across `.claude/`, `.agents/`, and `~/.gemini/`
- Periodic health checks of the developer automation matrix

## Invocation
```bash
${CLAUDE_PROJECT_DIR}/scripts/harness_check.sh
```

## Validation Matrix
The harness check runs three primary validation pillars:
1. **Hook & Guardrail Unit Test Suite (`tests/test_harness.sh`)**:
   - Deterministic Tier 3 invariant blocking (`rm -rf /`, `rm -rf ~`) with Exit 2
   - Windows host boundary isolation and read-only `/mnt/c/` path protection
   - Automated syntax linting gates (`bash -n`, `shellcheck`, `jq empty`, `py_compile`)
   - Lifecycle hook execution and error telemetry capture
2. **Multi-Agent Skill Symlink Sync (`scripts/sync_agent_skills.sh`)**:
   - Universal Agent standard relative symlinks (`.agents/skills/`)
   - Google Antigravity runtime symlinks (`~/.gemini/config/skills/`)
3. **Settings JSON Configuration Schema**:
   - Syntax validation of `.claude/settings.json` via `jq empty`

## Safety Classification
- **Tier 2 (Controlled System Operations)**: Executes non-destructive synthetic probes and verification test suites in isolated test environments.
