# /harness-check: Harness Self-Test & Diagnostic Matrix Command

Executes comprehensive synthetic probes and test suites validating Claude Code harness integrity.

## Invocation
```bash
${PROJECT_DIR:-.}/tests/test_harness.sh
```

## Description
Validates harness security and automation pillars:
- Security Guardrail Probes: Verifies deterministic blocking (`Exit 2`) on destructive commands (`rm -rf /`)
- Windows Host Boundary: Verifies blocking of modifications to Windows host directories
- Linter Integration: Verifies `shellcheck` execution on script edits
- Lifecycle Hooks: Verifies `session_preflight.sh`, `pre_tool_guard.sh`, `post_tool_lint.sh`, `post_tool_failure.sh`, `pre_compact_state.sh`, `session_cleanup.sh`
- Configuration Integrity: Validates `.claude/settings.json` schema and permissions
