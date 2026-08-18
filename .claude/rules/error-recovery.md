# Error Recovery & Auto-Healing Protocol

1. **Closed-Loop Auto-Healing**:
   - When a hook interrupts a tool execution with Exit Code 2, read the diagnostic output on `stderr` and perform an immediate repair turn.
   - For syntax errors (`bash -n`, `jq`, `python3 -m py_compile`), inspect the specific line mentioned in `stderr` and apply the fix.

2. **Graceful Degradation**:
   - If optional developer tools (e.g., `shellcheck`, `shfmt`) are absent, fall back to core bash and python built-in syntax validators.
