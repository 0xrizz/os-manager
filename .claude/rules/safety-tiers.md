# Safety Tiers & Action Classification

Execution classification and authorization boundaries enforced by the Claude Code PreToolUse guardrail engine.

## Tier 0: Autonomous Read-Only Operations (Exit Code 0)

Read-only inspection commands execute autonomously without confirmation or tool friction.

- **System Diagnostics**: `free -h`, `df -h`, `ps aux`, `uptime`, `uname -a`, `systemctl status <service>`.
- **Git Inspection**: `git status`, `git diff`, `git log`, `git branch`, `git rev-parse`.
- **File Discovery & Reading**: `ls`, `find`, `cat`, `grep`, `file`, and Claude Code `Read` / `Glob` / `Grep` tools.

## Tier 1: Workspace-Contained Modifications (Exit Code 0)

Modifications bounded strictly within `${CLAUDE_PROJECT_DIR}/` proceed autonomously, subject to post-tool linting gates.

- **Allowed Actions**: `Edit` and `Write` invocations targeting files within the workspace root.
- **Verification Gate**: Syntax validation (`bash -n`, `shellcheck`, `jq empty`, `python3 -m py_compile`) runs automatically upon file write.

## Tier 2: Controlled System Operations (Exit Code 0)

Whitelisted maintenance and automation scripts run with pre-authorized status.

- **Authorized Scripts**:
  - `./scripts/sys_diag.sh` (Health diagnostic engine)
  - `./scripts/clean_system.sh` (Safe cache and package cleanup)
  - `./scripts/update_runtimes.sh` (Runtime and toolchain coordinator)
  - `./scripts/wsl_snapshot.sh` (Disaster recovery tarball creator)
  - `./scripts/dotfiles_sync.sh` (Dotfiles backup, diff, and restore)
  - `./scripts/tmux_agents.sh` (Multi-agent paired workspace manager)
  - `./scripts/perf_tune.sh` (Filesystem I/O performance benchmark)
  - `./scripts/manage_timers.sh` (Systemd user timer manager)
  - `./scripts/harness_check.sh` (End-to-end harness self-test suite)

## Tier 3: Strict Invariant Violations (Hard Blocked with Exit Code 2)

Destructive or out-of-boundary operations are blocked deterministically by `scripts/hooks/pre_tool_guard.sh` with actionable diagnostic feedback on `stderr`.

1. **Root & Home Obliteration**:
   - `rm -rf /`, `rm -rf /*`, `rm -rf ~*`, `rm -rf $HOME`.
2. **WSL Lifecycle Termination**:
   - `wsl --unregister`, `wsl.exe --unregister`, `wsl --shutdown`.
3. **Package Manager Wildcard Purges**:
   - `apt purge *`, `apt remove -y *`.
4. **Raw Disk Partitioning & Formatting**:
   - `mkfs.*`, `fdisk`, `dd if=... of=/dev/sd*`.
5. **Windows Host Intrusions**:
   - Writing or editing `/mnt/c/Windows/**`, `Program Files/**`, `AppData/**`.
6. **Linux Core System Destruction**:
   - Writing or editing `/etc/passwd`, `/etc/shadow`, `/boot/**`, `/dev/**`.
