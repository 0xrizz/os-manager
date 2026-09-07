# /user-mode: Switch Agent to OS Management Co-Pilot Mode

Activates **User Mode** session-lock, transforming the agent into an autonomous OS Administrator and Co-Pilot for the host system while locking repository source code in a read-only state.

## Invocation
```bash
# In chat prompt:
/user-mode
```

## Description
When User Mode is activated:
- **Repository Code Lock**: All repository files (`os_manager/`, `tests/`, `scripts/`, `docs/`, `AGENTS.md`) become strictly read-only.
- **Dedicated Temp Workspace**: All Superpowers artifacts (specs, plans, runbooks, verification scripts) are routed exclusively to `temp/user-mode/` (`specs/`, `plans/`, `scripts/`).
- **Host Operations Scope**: The agent proactively manages hardware performance, CPU pinning/governor, hybrid GPU power-gating, 100% zRAM allocation, PipeWire audio routing, Debian package updates, and system diagnostics.
- **Safety Invariants**: Enforces non-interactive sudo execution (`./scripts/sudo_exec.sh`), zero password leakage, and protects persistent storage (`/mnt/data` or `/mnt/d`).
- **Session Duration**: The session lock persists for the remainder of the active conversation.
