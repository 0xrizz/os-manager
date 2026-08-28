# Non-Interactive Sudo & Terminal Execution Standards

Operational rules and protocols for elevated command execution within the `os-manager` workspace.

## 1. Absolute Rule: No Interactive Sudo

- **Failure Mode**: In Claude Code, tools execute in a non-interactive subshell without an attached TTY. Bare `sudo <cmd>` hangs waiting indefinitely on stdin or crashes immediately with `sudo: a terminal is required to read the password`.
- **Strict Prohibition**: NEVER issue bare `sudo <command>` directly via the `Bash` tool.

```bash
# ❌ STRICTLY FORBIDDEN (Hangs or crashes the agent session):
sudo apt-get update
sudo systemctl restart NetworkManager
sudo sysctl -p
sudo cp file.conf /etc/systemd/

# ✅ REQUIRED (Non-interactive execution):
./scripts/sudo_exec.sh apt-get update
./scripts/sudo_exec.sh systemctl restart NetworkManager
./scripts/sudo_exec.sh sysctl -p
./scripts/sudo_exec.sh cp file.conf /etc/systemd/
```

## 2. Standard Execution Protocols

### Protocol A (Preferred): Helper Script Wrapper
Use the repository execution wrapper [`scripts/sudo_exec.sh`](file:///scripts/sudo_exec.sh):
```bash
./scripts/sudo_exec.sh <command> [args...]
```
- Automatically verifies `sudo -n` caching.
- Safely resolves credentials from `.env` without printing or logging.
- Closes stdin and suppresses interactive prompts.

### Protocol B: Raw Non-Interactive Pipe (`sudo -S`)
When invoking directly in bash scripts or subshells:
```bash
if sudo -n true 2>/dev/null; then
    sudo <command>
else
    PASS=$(grep -E '^SUDO_PASSWORD=' "${CLAUDE_PROJECT_DIR:-.}/.env" | cut -d '=' -f2- || cat "${CLAUDE_PROJECT_DIR:-.}/.env" | tr -d '\r\n')
    echo "$PASS" | sudo -S <command>
fi
```
Or direct one-liner:
```bash
grep -E '^SUDO_PASSWORD=' "${CLAUDE_PROJECT_DIR:-.}/.env" | cut -d '=' -f2- | sudo -S <command>
```

## 3. Zero Password Leakage Invariant

- NEVER print, echo, or log the raw password or `.env` file contents to `stdout`, `stderr`, commit messages, reports, or transcript outputs.
- Suppress prompt output where possible (`sudo -S -p ''`).

## 4. Common Privileged Operations Recipes

| Task | Correct Command |
| :--- | :--- |
| **Package Update** | `./scripts/sudo_exec.sh apt-get update` |
| **Package Install** | `./scripts/sudo_exec.sh apt-get install -y <package>` |
| **Service Reload** | `./scripts/sudo_exec.sh systemctl daemon-reload` |
| **Service Restart** | `./scripts/sudo_exec.sh systemctl restart <service>` |
| **Kernel Sysctl** | `./scripts/sudo_exec.sh sysctl -w <key>=<val>` |
| **Apply Sysctl Conf** | `./scripts/sudo_exec.sh sysctl -p /etc/sysctl.d/<file>.conf` |
| **Write System File** | `./scripts/sudo_exec.sh install -m 644 <src> /etc/<dest>` |
| **File Permissions** | `./scripts/sudo_exec.sh chown -R root:root <path>` |

## 5. Error Recovery & Invariant Blocks

- If `pre_tool_guard.sh` returns **Exit Code 2** reporting `Interactive sudo detected`:
  - Do NOT retry bare `sudo`.
  - Immediately switch to `./scripts/sudo_exec.sh <command>`.
- If `sudo_exec.sh` reports missing credentials:
  - Verify `.env` existence in `${CLAUDE_PROJECT_DIR}/.env` or `${HOME}/dev/os-manager/.env`.
