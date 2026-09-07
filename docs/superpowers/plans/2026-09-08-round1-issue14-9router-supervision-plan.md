# Round 1: 9Router Process Supervision & Issue #14 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harmonize 9Router process supervision on GNOME 48 Wayland under mise and correct port specification in `AGENTS.md` to resolve GitHub Issue #14.

**Architecture:** Implement mise command resolution, TCP socket drain probe, multi-tier process teardown (systemd user unit -> GNOME transient scopes -> PID termination fallback), and socket release verification in `os_manager/commands/ai.py`. Align documentation in `AGENTS.md` and synchronize cross-mount state.

**Tech Stack:** Python 3.13 / 3.14, systemd user services & scopes, GNOME 48 Wayland, mise (npm:9router), unittest/pytest.

**Spec:** `docs/superpowers/specs/2026-09-08-mise-declarative-toolchain-architecture-design.md`

## Global Constraints

- Target platform: Debian GNU/Linux 13 (Trixie) 64-bit on Lenovo IdeaPad 3 15IIL05 (GNOME 48 on Wayland).
- Zero bare sudo: All privileged operations must strictly use `./scripts/sudo_exec.sh`.
- System Python protection: PEP 668 `/usr/bin/python3` must remain intact; use `.venv/bin/pytest`.
- 100% User-space execution: mise, 9router, and headroom run under UID 1000 (`rizz`).
- Cross-mount synchronization: When `AGENTS.md` is updated, sync to `/mnt/data/dev/os-manager/AGENTS.md`.
- No placeholders: Every step must contain exact code, command lines, and expected outputs.

---

### Task 1: Helpers for Mise Runner and Socket Drain Detection

**Files:**
- Modify: `os_manager/commands/ai.py`
- Test: `tests/test_ai_command.py`

**Interfaces:**
- Produces:
  - `get_mise_cmd(subcommand: str, *args: str) -> list[str]`
  - `is_port_in_use(port: int, host: str = "127.0.0.1") -> bool`

- [ ] **Step 1: Write the failing tests**

Add the following tests to `tests/test_ai_command.py`:

```python
    def test_is_port_in_use_true_and_false(self):
        """Verify is_port_in_use accurately checks socket binding."""
        from os_manager.commands.ai import is_port_in_use
        import socket

        # Test against a temporarily bound listening socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            s.listen(1)
            port = s.getsockname()[1]
            self.assertTrue(is_port_in_use(port))

        # Test against a port that is now closed
        self.assertFalse(is_port_in_use(port))

    @patch("shutil.which")
    @patch("os.path.isfile")
    @patch("os.access")
    def test_get_mise_cmd_with_mise_binary(self, mock_access, mock_isfile, mock_which):
        """Verify get_mise_cmd resolves mise executable when available."""
        from os_manager.commands.ai import get_mise_cmd

        mock_which.return_value = "/home/rizz/.local/bin/mise"
        mock_isfile.return_value = True
        mock_access.return_value = True

        cmd = get_mise_cmd("exec", "--", "9router", "--tray")
        self.assertEqual(cmd, ["/home/rizz/.local/bin/mise", "exec", "--", "9router", "--tray"])

    @patch("shutil.which", return_value=None)
    @patch("os.path.isfile", return_value=False)
    def test_get_mise_cmd_fallback_when_mise_missing(self, mock_isfile, mock_which):
        """Verify get_mise_cmd falls back to direct invocation when mise is absent."""
        from os_manager.commands.ai import get_mise_cmd

        cmd = get_mise_cmd("exec", "--", "9router")
        self.assertEqual(cmd, ["exec", "--", "9router"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/pytest tests/test_ai_command.py -k "test_is_port_in_use or test_get_mise_cmd" -v
```
Expected: FAIL with `ImportError: cannot import name 'is_port_in_use'` or `cannot import name 'get_mise_cmd'`.

- [ ] **Step 3: Implement minimal code in `os_manager/commands/ai.py`**

In `os_manager/commands/ai.py`, add imports (`import shutil`, `import socket`) and implement the helpers:

```python
def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a TCP port is currently open and bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def get_mise_cmd(subcommand: str, *args: str) -> list[str]:
    """Resolve mise executable and build deterministic command list."""
    mise_bin = shutil.which("mise") or os.path.expanduser("~/.local/bin/mise")
    if os.path.isfile(mise_bin) and os.access(mise_bin, os.X_OK):
        return [mise_bin, subcommand] + list(args)
    return [subcommand] + list(args)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
.venv/bin/pytest tests/test_ai_command.py -k "test_is_port_in_use or test_get_mise_cmd" -v
```
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/ai.py tests/test_ai_command.py
git commit -m "feat(ai): add is_port_in_use and get_mise_cmd helpers"
```

---

### Task 2: Multi-Tier Coordinated Stop & Socket Drain Gate in `manage_services`

**Files:**
- Modify: `os_manager/commands/ai.py`
- Test: `tests/test_ai_command.py`

**Interfaces:**
- Consumes: `is_port_in_use`, `get_mise_cmd`
- Produces:
  - `find_gnome_9router_scopes() -> list[str]`
  - `find_9router_pids() -> list[int]`
  - Enhanced `manage_services(action="stop")` with transient scope cleanup, PID fallback, and 3s socket drain gate.

- [ ] **Step 1: Write the failing tests**

Add the following tests to `tests/test_ai_command.py`:

```python
    @patch("subprocess.run")
    def test_find_gnome_9router_scopes(self, mock_run):
        """Verify discovery of active GNOME transient scopes for 9router."""
        from os_manager.commands.ai import find_gnome_9router_scopes

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="app-gnome-9router-2511.scope loaded active running 9router\n"
        )
        scopes = find_gnome_9router_scopes()
        self.assertEqual(scopes, ["app-gnome-9router-2511.scope"])

    @patch("subprocess.run")
    def test_find_9router_pids(self, mock_run):
        """Verify discovery of 9router PIDs via pgrep."""
        from os_manager.commands.ai import find_9router_pids

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="2511\n4096\n"
        )
        pids = find_9router_pids()
        self.assertEqual(pids, [2511, 4096])

    @patch("time.sleep")
    @patch("os_manager.commands.ai.is_port_in_use")
    @patch("os_manager.commands.ai.find_9router_pids")
    @patch("os_manager.commands.ai.find_gnome_9router_scopes")
    @patch("subprocess.run")
    def test_manage_services_stop_full_flow(
        self, mock_run, mock_scopes, mock_pids, mock_port, mock_sleep
    ):
        """Verify manage_services('stop') executes static units, scopes, and verifies drain."""
        from os_manager.commands.ai import manage_services

        mock_scopes.return_value = ["app-gnome-9router-2511.scope"]
        mock_pids.return_value = []
        # Port initially in use, then freed
        mock_port.side_effect = [True, False]
        mock_run.return_value = MagicMock(returncode=0)

        code = manage_services("stop")
        self.assertEqual(code, 0)

        # Verify GNOME scope was stopped
        mock_run.assert_any_call(["systemctl", "--user", "stop", "app-gnome-9router-2511.scope"], check=False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/pytest tests/test_ai_command.py -k "test_find_gnome or test_find_9router or test_manage_services_stop_full_flow" -v
```
Expected: FAIL with `ImportError: cannot import name 'find_gnome_9router_scopes'`.

- [ ] **Step 3: Implement multi-tier stop in `os_manager/commands/ai.py`**

In `os_manager/commands/ai.py`, add imports (`import signal`, `import time`) and implement `find_gnome_9router_scopes`, `find_9router_pids`, and enhance `manage_services`:

```python
def find_gnome_9router_scopes() -> list[str]:
    """Discover active GNOME transient scopes associated with 9router."""
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "list-units", "--type=scope", "--state=active", "--no-legend", "app-gnome-9router-*.scope"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            scopes = []
            for line in proc.stdout.splitlines():
                parts = line.strip().split()
                if parts and parts[0].endswith(".scope"):
                    scopes.append(parts[0])
            return scopes
    except Exception:
        pass
    return []


def find_9router_pids() -> list[int]:
    """Find process IDs running 9router via pgrep."""
    try:
        proc = subprocess.run(
            ["pgrep", "-f", "9router"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            my_pid = os.getpid()
            pids = []
            for line in proc.stdout.splitlines():
                line = line.strip()
                if line.isdigit():
                    pid = int(line)
                    if pid != my_pid:
                        pids.append(pid)
            return pids
    except Exception:
        pass
    return []


def stop_ai_services() -> int:
    """Multi-tier coordinated stop sequence for Headroom and 9Router."""
    print("-> Stopping Headroom proxy...")
    subprocess.run(["systemctl", "--user", "stop", "headroom-default.service"], check=False)

    print("-> Stopping 9Router gateway (static systemd units)...")
    subprocess.run(["systemctl", "--user", "stop", "app-9router@autostart.service", "app-9router.service"], check=False)

    # Clean GNOME 48 transient scopes
    scopes = find_gnome_9router_scopes()
    if scopes:
        for scope in scopes:
            print(f"-> Stopping GNOME transient scope: {scope}...")
            subprocess.run(["systemctl", "--user", "stop", scope], check=False)

    # PID Fallback if port 20128 is still in use
    if is_port_in_use(20128):
        pids = find_9router_pids()
        if pids:
            print(f"-> Port 20128 still bound; sending SIGTERM to PIDs: {pids}...")
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            time.sleep(1.0)
            if is_port_in_use(20128):
                print(f"-> Port 20128 still bound; escalating to SIGKILL for PIDs: {pids}...")
                for pid in pids:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    # Socket Drain Gate (up to 3.0 seconds)
    drain_deadline = time.time() + 3.0
    drained = False
    while time.time() < drain_deadline:
        if not is_port_in_use(20128):
            drained = True
            break
        time.sleep(0.2)

    if drained:
        print("[OK] Services stopped and port 20128 released.")
        return 0
    else:
        print("[Warning] Services stop dispatched, but port 20128 did not release within timeout.")
        return 1
```

Wire `stop_ai_services()` into `manage_services(action="stop")`.

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
.venv/bin/pytest tests/test_ai_command.py -k "test_find_gnome or test_find_9router or test_manage_services_stop_full_flow" -v
```
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/ai.py tests/test_ai_command.py
git commit -m "feat(ai): implement multi-tier stop and socket drain gate for 9router"
```

---

### Task 3: Pre-flight Check, Mise-Native Start & Restart Coordination

**Files:**
- Modify: `os_manager/commands/ai.py`
- Test: `tests/test_ai_command.py`

**Interfaces:**
- Consumes: `is_port_in_use`, `get_mise_cmd`, `stop_ai_services`
- Produces:
  - `start_ai_services() -> int`
  - Enhanced `manage_services(action="start")`
  - Enhanced `manage_services(action="restart")`

- [ ] **Step 1: Write the failing tests**

Add the following tests to `tests/test_ai_command.py`:

```python
    @patch("os_manager.commands.ai.check_gateway_health")
    @patch("os_manager.commands.ai.is_port_in_use", return_value=True)
    def test_start_ai_services_already_running(self, mock_port, mock_health):
        """Verify start_ai_services skips launch if 9router is already healthy."""
        from os_manager.commands.ai import start_ai_services

        mock_health.return_value = {
            "headroom": {"online": True},
            "router": {"online": True},
        }
        code = start_ai_services()
        self.assertEqual(code, 0)

    @patch("subprocess.run")
    @patch("os_manager.commands.ai.check_gateway_health")
    @patch("os_manager.commands.ai.is_port_in_use", return_value=False)
    @patch("os_manager.commands.ai.get_mise_cmd")
    def test_start_ai_services_launches_under_mise(self, mock_mise, mock_port, mock_health, mock_run):
        """Verify start_ai_services falls back to launching 9router via mise when unit is missing."""
        from os_manager.commands.ai import start_ai_services

        mock_mise.return_value = ["/home/rizz/.local/bin/mise", "exec", "--", "9router", "--tray", "--skip-update"]
        # systemctl start app-9router@autostart fails with code 1
        mock_run.side_effect = [
            MagicMock(returncode=1),  # systemctl start app-9router@autostart
            MagicMock(returncode=0),  # systemd-run --user --unit=app-9router ...
            MagicMock(returncode=0),  # systemctl start headroom-default
        ]
        mock_health.return_value = {
            "headroom": {"online": True},
            "router": {"online": True},
        }

        code = start_ai_services()
        self.assertEqual(code, 0)
        # Verify systemd-run was called with mise command
        mock_run.assert_any_call(
            ["systemd-run", "--user", "--unit=app-9router", "--", "/home/rizz/.local/bin/mise", "exec", "--", "9router", "--tray", "--skip-update"],
            check=False
        )

    @patch("os_manager.commands.ai.start_ai_services", return_value=0)
    @patch("os_manager.commands.ai.stop_ai_services", return_value=0)
    def test_manage_services_restart_calls_stop_then_start(self, mock_stop, mock_start):
        """Verify manage_services('restart') cleanly chains stop and start."""
        from os_manager.commands.ai import manage_services

        code = manage_services("restart")
        self.assertEqual(code, 0)
        mock_stop.assert_called_once()
        mock_start.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/pytest tests/test_ai_command.py -k "test_start_ai_services or test_manage_services_restart" -v
```
Expected: FAIL with `ImportError: cannot import name 'start_ai_services'`.

- [ ] **Step 3: Implement start and restart logic in `os_manager/commands/ai.py`**

In `os_manager/commands/ai.py`, implement `start_ai_services()` and wire into `manage_services`:

```python
def start_ai_services() -> int:
    """Pre-flight check and coordinated start for 9Router and Headroom."""
    health = check_gateway_health()
    if health["router"]["online"] and is_port_in_use(20128):
        print("[OK] 9Router gateway is already online on port 20128.")
    else:
        print("-> Starting 9Router gateway...")
        # First try static autostart unit
        res_r = subprocess.run(["systemctl", "--user", "start", "app-9router@autostart.service"], check=False)
        if res_r.returncode != 0:
            # Fallback to systemd-run with mise runner
            mise_cmd = get_mise_cmd("exec", "--", "9router", "--tray", "--skip-update")
            run_cmd = ["systemd-run", "--user", "--unit=app-9router", "--"] + mise_cmd
            print(f"   [Notice] Launching via systemd-run with mise: {' '.join(mise_cmd)}")
            res_run = subprocess.run(run_cmd, check=False)
            if res_run.returncode != 0:
                print("   [Fallback] Launching background process via mise directly...")
                try:
                    subprocess.Popen(mise_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                except Exception as exc:
                    print(f"   [Error] Failed to spawn 9Router process: {exc}")

    if health["headroom"]["online"] and is_port_in_use(8787):
        print("[OK] Headroom proxy is already online on port 8787.")
    else:
        print("-> Starting Headroom proxy...")
        res_h = subprocess.run(["systemctl", "--user", "start", "headroom-default.service"], check=False)
        if res_h.returncode != 0:
            print("   [Warning] Headroom proxy service start returned non-zero exit code.")

    print("[OK] Services start sequence completed.")
    return 0
```

Update `manage_services`:
```python
def manage_services(action: str) -> int:
    """Supervise background services via systemctl user or fallback process."""
    print(f"=== AI Gateway Service Manager ({action}) ===")
    if action == "start":
        return start_ai_services()
    elif action == "stop":
        return stop_ai_services()
    elif action == "restart":
        res_stop = stop_ai_services()
        res_start = start_ai_services()
        return 0 if (res_stop == 0 and res_start == 0) else 1
    elif action == "logs":
...
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
.venv/bin/pytest tests/test_ai_command.py -k "test_start_ai_services or test_manage_services_restart" -v
```
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add os_manager/commands/ai.py tests/test_ai_command.py
git commit -m "feat(ai): integrate mise-native start and coordinated restart in manage_services"
```

---

### Task 4: Documentation Alignment & Cross-Mount Synchronization

**Files:**
- Modify: `AGENTS.md:296-300`
- Target Sync: `/mnt/data/dev/os-manager/AGENTS.md`

**Interfaces:**
- Corrects port specification from `3000` to `20128` in Pillar VII Section 7.4.
- Synchronizes file to persistent data mount `/mnt/data/dev/os-manager/`.

- [ ] **Step 1: Check existing port reference in `AGENTS.md`**

Run:
```bash
grep -n "9Router.*port" AGENTS.md
```
Expected: `297:* **9Router:** Multi-model proxy routing across cloud and local models (port `3000`).`

- [ ] **Step 2: Update `AGENTS.md` Section 7.4**

Change line 297 from:
```markdown
* **9Router:** Multi-model proxy routing across cloud and local models (port `3000`).
```
To:
```markdown
* **9Router:** Multi-model proxy routing across cloud and local models (port `20128`).
```

- [ ] **Step 3: Synchronize to `/mnt/data/dev/os-manager/AGENTS.md`**

Run:
```bash
if [ -d "/mnt/data/dev/os-manager" ]; then
    cp -u /home/rizz/dev/os-manager/AGENTS.md /mnt/data/dev/os-manager/AGENTS.md
    echo "Synced AGENTS.md to /mnt/data/dev/os-manager/AGENTS.md"
fi
```
Verify:
```bash
grep "port \`20128\`" /mnt/data/dev/os-manager/AGENTS.md
```
Expected: Match found.

- [ ] **Step 4: Run full test suite for `ai` command and launcher**

Run:
```bash
.venv/bin/pytest tests/test_ai_command.py tests/test_ai_claude.py -v
```
Expected: 100% PASS across all unit tests (at least 14 tests).

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md
git commit -m "docs(governance): correct 9Router port specification to 20128 in AGENTS.md"
```

---

### Task 5: End-to-End Verification & Issue #14 Resolution Validation

**Files:**
- System test and diagnostics verification

- [ ] **Step 1: Verify `osm ai status --json` output**

Run:
```bash
PYTHONPATH=. .venv/bin/python -m os_manager.cli ai status --json
```
Expected: Output includes `"health"` dictionary with `"headroom"` and `"router"` statuses, and cumulative `"telemetry"`.

- [ ] **Step 2: Verify `osm ai --help` output**

Run:
```bash
PYTHONPATH=. .venv/bin/python -m os_manager.cli ai --help
```
Expected: Valid help output listing `status`, `dashboard`, `start`, `stop`, `restart`, `logs`, `claude`.

- [ ] **Step 3: Close GitHub Issue #14 reference and verify git log**

Run:
```bash
git log -n 4 --oneline
```
Expected: Clean commits for Tasks 1–4.
All changes self-contained and ready for Round 2.
