# AGENTS.md

Operational governance, architectural invariants, safety guardrails, and execution standards for AI agents (Antigravity CLI `agy`, Claude Code, subagents, and automated harnesses) operating in the `os-manager` ecosystem across Debian GNU/Linux 13 (Trixie) Bare-Metal and Debian WSL2 environments.

---

## Hardware & Target System Architecture

* **Machine Model:** Lenovo IdeaPad 3 15IIL05 (81WD)
* **Processor:** Intel Core i5-1035G1 (Ice Lake, 4C/8T, 1.00 GHz base / 3.60 GHz boost)
* **Graphics (Hybrid):** Intel Iris Plus Graphics G1 (Integrated) + NVIDIA GeForce MX330 2GB VRAM (Discrete)
* **System Memory:** 8 GB DDR4 (1x 4GB Soldered + 1x 4GB SODIMM @ 2667 MHz)
* **Primary Storage:** 512 GB NVMe SSD (`/dev/nvme0n1`)
* **Operating System:** Debian GNU/Linux 13 (Trixie) 64-bit with Linux Kernel 6.12+
* **Desktop Environment:** GNOME 48 on Wayland
* **Audio Engine:** PipeWire + WirePlumber with Realtek ALC298 codec
* **Wireless Subsystem:** Intel Wireless-AC 9560 160MHz (`iwlwifi`)

---

## Pillar I: Absolute Safety & Zero-Data-Loss Guardrails

### 1.1 In-Place Persistent Storage Protection (`/dev/nvme0n1p4` / Drive D:)
* **Rule:** Partition `/dev/nvme0n1p4` (labeled `DATA_STORE`, mounted at `/mnt/data` on Bare Metal and `/mnt/d` on WSL2) hosts ~201 GB of critical user data. It MUST be treated as immutable, in-place persistent storage.
* **Strict Prohibition:** NEVER execute formatting, partition wiping, file system creation, partition deletion, or broad recursive deletion on this partition (`wipefs`, `mkfs`, `mkfs.ext4`, `mkfs.ntfs`, `fdisk d`, `parted rm`, `rm -rf /mnt/data/*`).
* **Path Duality Invariant:**
  * **Debian WSL2:** Mount location is `/mnt/d/`.
  * **Bare-Metal Debian:** Mount location is `/mnt/data/`.
  * Always verify mount presence before referencing paths in scripts.

```bash
# BAD (Catastrophic - Destroys user data):
mkfs.ext4 /dev/nvme0n1p4
wipefs -a /dev/nvme0n1p4

# GOOD (Safe verification & non-destructive mounting):
lsblk -f /dev/nvme0n1p4
grep -E '/mnt/data|/mnt/d' /proc/mounts || true
```

### 1.2 Zero-USB Architecture Invariant
* **Rule:** All operating system installations, kernel kexec transitions, loopback staging, kernel/bootloader maintenance, and disaster recovery MUST be 100% Zero-USB.
* **Prohibition:** Dictionaries, prompts, scripts, or implementation plans MUST NEVER assume, require, or prompt for physical external USB thumb drives.
* **Mechanism:** Utilize local staging partitions (`DEBIAN_SET`), loopback ISO mounting, and GRUB loopback/kexec mechanisms for bare-metal transitions.

### 1.3 Safe Partition Reclamation & Expansion Sequence
* **Rule:** Reclaiming space from legacy partitions (e.g., old Windows OS partition `nvme0n1p3`) is only permitted after the bare-metal system has completed a minimum of 2–3 successful cold reboots and all critical hardware components (Wi-Fi, Audio, GPU, Suspend/Resume) have passed verification.
* **Expansion Standard:** Online partition resizing must strictly follow the non-destructive order:
  1. `sudo growpart /dev/nvme0n1 <partition_number>`
  2. `sudo resize2fs /dev/nvme0n1p<partition_number>` (for ext4)

### 1.4 Human Confirmation Gate for Destructive Operations
* **Rule:** Any unrecoverable disk partition table modification (`fdisk`, `parted`, `gdisk`) requires explicit human confirmation before invocation.

---

## Pillar II: Interoperability & Command Execution Standards

### 2.1 Non-Interactive Sudo & Terminal Execution (Zero-Stall Standard)
* **Failure Mode (Root Cause):** In non-interactive agent environments without an attached TTY, executing bare `sudo <cmd>` hangs indefinitely waiting on stdin or crashes immediately with `sudo: a terminal is required to read the password`.
* **Strict Prohibition:** NEVER execute bare interactive `sudo <command>`.
* **Primary Standard (Preferred):** Use the repository execution wrapper [`scripts/sudo_exec.sh`](file:///home/rizz/dev/os-manager/scripts/sudo_exec.sh):
  ```bash
  ./scripts/sudo_exec.sh <command> [args...]
  ```
* **Secondary Standard (Direct Non-Interactive Pipe):**
  ```bash
  grep -E '^SUDO_PASSWORD=' /home/rizz/dev/os-manager/.env | cut -d '=' -f2- | sudo -S <command>
  ```
* **Zero Password Leakage:** NEVER echo, print, or log `.env` contents or the raw password to stdout, stderr, reports, or transcripts.

```bash
# BAD (Fails with TTY error or hangs session):
sudo apt-get update
sudo systemctl restart NetworkManager
sudo sysctl -p

# GOOD (Secure, non-interactive execution):
./scripts/sudo_exec.sh apt-get update
./scripts/sudo_exec.sh systemctl restart NetworkManager
./scripts/sudo_exec.sh sysctl -p
```

#### Privileged Operation Recipes
| Operation | Standard Non-Interactive Command |
| :--- | :--- |
| **Package Management** | `./scripts/sudo_exec.sh apt-get update && ./scripts/sudo_exec.sh apt-get install -y <pkg>` |
| **Service Control** | `./scripts/sudo_exec.sh systemctl daemon-reload && ./scripts/sudo_exec.sh systemctl restart <service>` |
| **Sysctl Kernel Tuning** | `./scripts/sudo_exec.sh sysctl -w <key>=<val>` or `./scripts/sudo_exec.sh sysctl -p <file>` |
| **System File Writes** | `./scripts/sudo_exec.sh install -m 644 <src> /etc/<dest>` or `./scripts/sudo_exec.sh cp <src> <dest>` |
| **Hardware / DMI Access** | `./scripts/sudo_exec.sh dmidecode -s system-product-name` |

### 2.2 Non-Interactive Windows Binary Execution in WSL (`stdin` Closure)
* **Failure Mode:** In WSL2, invoking Windows PE binaries (`powershell.exe`, `cmd.exe`, `manage-bde.exe`, `chkdsk.exe`, `fsutil.exe`, `diskpart.exe`) without a connected interactive TTY causes the subshell to hang indefinitely waiting for input.
* **Mandatory Standard:** Always close `stdin` using `< /dev/null` and pass explicit non-interactive flags.

```bash
# BAD (Hangs the agent indefinitely):
powershell.exe -Command "Get-BitLockerVolume"
/mnt/c/Windows/System32/cmd.exe /c "powercfg /h off"

# GOOD (Resilient non-interactive execution):
/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe -NoProfile -NonInteractive -Command "Get-BitLockerVolume" < /dev/null
/mnt/c/Windows/System32/cmd.exe /c "powercfg /h off" < /dev/null
```

### 2.3 CMD.EXE UNC Path Isolation
* **Failure Mode:** `cmd.exe` does not support WSL UNC network paths (`\\wsl.localhost\Debian\...`) as current working directories, returning `CMD.EXE was started with the above path as the current directory. UNC paths are not supported.`
* **Mandatory Standard:** When invoking `cmd.exe`, explicitly switch working directory to a Windows drive path (e.g., `cd /mnt/c` or `/mnt/d`) or invoke with clean path redirects.

```bash
# BAD (Fails with UNC path error):
cd /home/rizz/dev/os-manager && cmd.exe /c "dir" < /dev/null

# GOOD:
(cd /mnt/c && /mnt/c/Windows/System32/cmd.exe /c "dir" < /dev/null)
```

### 2.4 CLI Binary & Path Resolution (`~/.local/bin` & PATH)
* **Standard:** User-space utilities (`osm`, `headroom`, `uv`, `node`, `pnpm`) reside in `~/.local/bin` or user directories. Non-interactive subshells may not load login shell dotfiles.
* Always prepend `export PATH="$HOME/.local/bin:$PATH"` or call absolute paths (`~/.local/bin/osm`) in scripts and instructions.

```bash
# BAD (Fails with 'osm: command not found'):
osm tune all --audit

# GOOD:
export PATH="$HOME/.local/bin:$PATH"
osm tune all --audit
# Or direct invocation:
~/.local/bin/osm tune all --audit
```

---

## Pillar III: 4-Tier Security Matrix & Zero-Trust Governance

Lifecycle hooks in `scripts/hooks/` and `os_manager/security/ast_guard.py` enforce strict execution tiers across all agent interfaces:

1. **Tier 0 (Autonomous Read-Only - Exit 0 / Allow)**: Non-mutating inspections (`git status`, `df`, `ps`, `uptime`, `osm diag`, `view_file`, `list_dir`, `grep_search`).
2. **Tier 1 (Workspace Contained - Exit 0 / Allow)**: File modifications strictly bounded within workspace root, validated post-tool via linters (`bash -n`, `python3 -m py_compile`, `jq empty`).
3. **Tier 2 (Controlled Operations - Exit 0 / Allow)**: Whitelisted automation scripts (`./scripts/*.sh`, `osm` CLI commands) run pre-authorized.
4. **Tier 3 (Strict Invariants - Hard Block with Exit 2 / Deny)**:
   - **Interactive Sudo**: Bare `sudo <cmd>` without `-S` or `sudo_exec.sh` is caught and blocked before hanging.
   - **Root / Home Obliteration**: `rm -rf /`, `rm -rf ~`, `rm -rf $HOME`.
   - **WSL Lifecycle Destruction**: `wsl --unregister`, `wsl.exe --shutdown`.
   - **Package Manager Wildcard Purges**: `apt purge *`, `pacman -Rcs *`, `dnf remove --all`, `zypper remove *`.
   - **Privileged Container Escapes**: `podman run --privileged`, `docker run --privileged`.
   - **Raw Disk Partitioning / Formatting**: `mkfs.*`, `fdisk`, `dd if=... of=/dev/sd*`.
   - **Protected Path Writes**: Modifying `/mnt/c/Windows`, `/mnt/data/`, `/etc/shadow`, `/boot/`, `/dev/`.

---

## Pillar IV: Core CLI Controllers (`osm`) & Development Commands

### Core CLI Commands (`osm`)
* `osm mcp serve`: Launch asynchronous JSON-RPC 2.0 stdio MCP server daemon
* `osm mcp install [--client all|claude|cursor|antigravity]`: Auto-configure MCP client settings
* `osm mcp tools`: Inspect available MCP tool declarations
* `osm check [--json]`: Run master harness test suite (95+ assertions)
* `osm diag [--json]`: Gather real-time system, platform, and DMI diagnostics
* `osm tune [status|apply|revert]`: Tune CPU governor, I/O schedulers, memory, and platform profiles
* `osm psi [status|compact|monitor|daemon]`: Autonomous Linux PSI stall feedback & zRAM compaction
* `osm cpu [topology|audit|run|pin]`: Heterogeneous CPU affinity router & P/E-core partitioning
* `osm gpu [status|install|run|sync-profiles|profile]`: Dual-GPU subsystem management & workload router
* `osm hsi [audit|apply [--dry-run]]`: Host Security ID hardware & firmware hardening
* `osm ai [status|start|stop|restart|configure]`: Unified AI gateway (Headroom & 9Router)
* `osm clean [--dry-run|--all]`: Evict package manager caches and temp files
* `osm perf`: Empirical benchmarks for storage I/O, memory, and CPU
* `osm upgrade`: Debian 13 (Trixie) upgrade coordination engine
* `osm init [--global|--project <dir>]`: Initialize harness and hook configurations

### Testing and Validation Matrix
* **Master Harness Test Suite (95+ assertions):** `bash tests/test_harness.sh`
* **Harness Isolation & Host Hygiene Test:** `bash tests/test_harness_isolation.sh`
* **Full Harness Self-Check:** `bash scripts/harness_check.sh`
* **Complete Pytest Suite:** `.venv/bin/pytest tests/`
* **Claude-to-Antigravity Naturalizer:** `python3 scripts/naturalize_antigravity_harness.py`

---

## Pillar V: Performance, Context Hygiene & Anti-Spinning Rules

### 5.1 Reactive Wakeup vs. Strict Ban on Polling Loops
* **Failure Mode (Root Cause):** Historical session audits identified 800+ redundant steps where agents executed tight loops of `schedule` (10s timers), `manage_task status`, and `view_file` to poll long-running background tasks (e.g. `chkdsk`, `tar`, `apt-get`).
* **Architecture Invariant:** Antigravity CLI and harnesses feature automatic reactive wakeup. When a background task or subagent finishes, the harness automatically wakes the agent.
* **Strict Rule:** NEVER construct polling loops.
  1. Launch background tasks with sufficient `WaitMsBeforeAsync` (5000–10000 ms).
  2. If the task continues asynchronously in the background, output a brief status note to the user and STOP calling tools. Wait for the system's reactive notification.

```text
# BAD (Anti-Pattern - 800+ wasted turns):
run_command(cmd, WaitMsBeforeAsync=500) -> returns task-123
schedule(DurationSeconds=10, Prompt="Check task") -> tool call
manage_task(Action="status", TaskId="task-123") -> tool call
view_file(log_file) -> tool call
[Repeat 100 times]

# GOOD (Reactive Execution):
run_command(cmd, WaitMsBeforeAsync=5000) -> task moves to background
Output: "Process launched in background. Awaiting completion notification..."
[End Turn - No more tool calls. Harness awakens agent on completion.]
```

### 5.2 300-Step Session Lifecycle & Checkpoint Protocol
* **Root Cause:** Sessions approaching **250–300+ steps** experience severe latency, token context saturation, and stream interruptions.
* **Standard Execution Boundary:**
  1. Do NOT initiate large new implementation plans or multi-task SDD runs inside a high-step session.
  2. When a major phase, benchmark, or SDD plan finishes, compile the current system status into `.agents/HANDOFF.md` or `.claude/temp/HANDOFF.md` (following `HANDOFF.template.md`).
  3. Explicitly advise the user to start a fresh Antigravity/Claude session.

### 5.3 Subagent Brief & Report Isolation Contract
* **Rule:** Subagents (implementers, reviewers) must maintain clean context boundaries.
  * **File-Based Memory:** Subagents must write verbose logs, terminal outputs, diffs, and verification transcripts to designated report files (`task-N-report.md`, `review-report.md`).
  * **Compact Contract:** Direct subagent responses to the parent controller are strictly limited to concise summary contracts (VERDICT, commit hashes, 1-line test summary, and blockers/concerns).
  * Subagents must never spawn subagents.

### 5.4 Safe File Modification Standards
* **File Overwrites:** For complete file rewrites or documents larger than 100 lines, use `write_to_file` with `Overwrite: true`. Do NOT attempt massive contiguous replacements using `replace_file_content`.
* **Artifact Metadata Scope:** The `ArtifactMetadata` parameter is strictly reserved for user-facing artifacts in the brain directory (`<appDataDir>/brain/<conversation-id>`). NEVER attach `ArtifactMetadata` to standard project codebase files.

---

## Pillar VI: Environment, Python Runtime & System Boundaries

### 6.1 Debian System Python Protection (`/usr/bin/python3` & PEP 668)
* **System Boundary:** Debian 13 Trixie uses Python 3.13 to manage GNOME Shell, systemd integrations, and system-level utilities.
* **Prohibitions:**
  * NEVER overwrite, replace, or re-link `/usr/bin/python3`.
  * NEVER execute global `pip install` without `--break-system-packages` or outside of virtual environments.
* **Environment Isolation:**
  * Project dependencies for `os-manager` MUST be isolated in `/home/rizz/dev/os-manager/.venv`.
  * All CLI tests and scripts must execute using `.venv/bin/pytest` or with `.venv/bin/python`.
  * Custom standalone runtimes must be managed via `uv` or `pyenv` in user-space (`~/.local/`).

```bash
# BAD (Corrupts Debian system packages):
pip install -r requirements.txt
python3 -m pip install pytest

# GOOD (Isolated virtualenv execution):
/home/rizz/dev/os-manager/.venv/bin/pytest tests/ -v
# Or via UV:
uv run --project /home/rizz/dev/os-manager pytest tests/ -v
```

### 6.2 Dual-Harness Architecture & Cross-Mount Synchronization
* **Dual-Harness Architecture:**
  * **Claude Code Harness:** `.claude/` (`skills/`, `commands/`, `rules/`, `agents/`, `settings.json`).
  * **Antigravity Harness:** `.agents/` (`skills/`, `workflows/`, `rules/`, `agents/`, `hooks.json`).
  * Skills and workflows remain strictly scoped within project workspaces without polluting `$HOME`.
* **Cross-Mount Repository Synchronization:**
  * Whenever `AGENTS.md`, `docs/LINUX_MIGRATION_BLUEPRINT.md`, or `.agents/HANDOFF.md` are updated in `/home/rizz/dev/os-manager/`, synchronize them to:
    * `/mnt/data/dev/os-manager/` (Bare-Metal Linux)
    * `/mnt/d/dev/os-manager/` (Debian WSL2, if available)

```bash
# Automated Synchronization Snippet:
SYNC_TARGET=""
if [ -d "/mnt/data/dev/os-manager" ]; then
  SYNC_TARGET="/mnt/data/dev/os-manager"
elif [ -d "/mnt/d/dev/os-manager" ]; then
  SYNC_TARGET="/mnt/d/dev/os-manager"
fi

if [ -n "$SYNC_TARGET" ]; then
  cp -u /home/rizz/dev/os-manager/AGENTS.md "$SYNC_TARGET/AGENTS.md" 2>/dev/null || true
  cp -u /home/rizz/dev/os-manager/.agents/HANDOFF.md "$SYNC_TARGET/.agents/HANDOFF.md" 2>/dev/null || true
fi
```

---

## Pillar VII: Hardware-Specific Operational Knowledge & Trixie Tuning Matrix

### 7.1 Realtek ALC298 Audio & PipeWire / WirePlumber Tuning
* **Hardware Codec:** Realtek ALC298 on Lenovo IdeaPad 3 (81WD).
* **Audio Routing Standards:**
  * Master & Speaker ALSA channels must remain unmuted and balanced via `amixer -c 0 sset Speaker unmute 100%`.
  * PipeWire sink volume and default routing are inspected via `wpctl status` and `wpctl inspect <ID>`.
  * Channel balance and volume persistence are preserved across reboots via `alsa-restore.service` (`sudo alsactl store`).
  * Avoid conflicting software DSP plugins (e.g. EasyEffects spatializers) that introduce phase cancellation or echo on laptop integrated speakers.

### 7.2 Memory & Storage Tuning (zRAM 100% & Sysctl Persistence)
* **zRAM Scaling Standard:** Fast compressed in-memory swap using `zram-tools` configured with `ALGO=zstd` and `PERCENT=100` (8 GB zRAM on 8 GB physical RAM).
* **Kernel Sysctl Profile:**
  * `vm.swappiness=180` (aggressive zRAM utilization to preserve physical RAM for active pages).
  * `vm.dirty_ratio=10` and `vm.dirty_background_ratio=5` (smooth background page writeout to NVMe).
  * `vm.vfs_cache_pressure=50` (preserve inode and dentry caches).
  * Persistent configuration stored in `/etc/sysctl.d/99-osm-system.conf` and `/etc/default/zramswap`.

### 7.3 Network & Hybrid GPU Power Management
* **Wi-Fi Firmware:** Intel Wireless-AC 9560 requires `firmware-iwlwifi` (`iwlwifi-Qu-*.ucode`). Avoid disabling 802.11ac hardware crypto.
* **Hybrid GPU Power-Gating:** NVIDIA MX330 discrete GPU must stay in runtime D3hot/D3cold power state when idle via `udev` rules and `system76-power` / `bumblebee` / `prime-select` profiles, preventing battery drain and thermal throttling on the Ice Lake CPU.

### 7.4 AI Tool Proxy & Multi-Model Routing Mesh
* **9Router:** Multi-model proxy routing across cloud and local models (port `3000`).
* **Headroom:** Context compression and token reducer proxy (port `8787`).
* Claude Code and Antigravity agents route through local proxy endpoints using standard environment configuration (`ANTHROPIC_BASE_URL=http://127.0.0.1:8787`).
