# Safety Tiers & Action Classification

1. **Tier 0 (Autonomous Read-Only)**:
   - System state inspection (`free`, `df`, `systemctl status`, `git status`, `ps`, read-only diagnostics) may run autonomously without friction.

2. **Tier 1 (Workspace Contained)**:
   - Modifications inside `/home/rizz/dev/os-manager/` are safe and autonomous, subject to post-tool linting.

3. **Tier 2 (Controlled System Operations)**:
   - Standard maintenance scripts (`sys_diag.sh`, `clean_system.sh`, `update_runtimes.sh`, `wsl_snapshot.sh`) are authorized.

4. **Tier 3 (Strict Invariant Violations - Hard Blocked)**:
   - Deletions of `/` or `~`, WSL termination commands (`wsl --unregister`), wildcard package purges (`apt purge *`), and direct disk formatting (`mkfs.*`) are blocked deterministically.
