# Network & Socket Subsystem Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Linux network and socket subsystem tuning (`net.core.default_qdisc = fq_codel`, `net.ipv4.tcp_congestion_control = bbr`, `tcp_fastopen = 3`, `somaxconn = 8192`) in `os_manager` with atomic snapshots, audit reporting, and CLI routing.

**Architecture:** Add network configuration generator, audit inspector, and apply/revert orchestration to `os_manager/commands/tune.py`. Expose the interface via CLI parser `osm tune network` and integrate into master telemetry and `osm tune system`.

**Tech Stack:** Python 3.11+ (Standard Library `argparse`, `pathlib`, `subprocess`, `unittest`), Linux Kernel sysctl (`/etc/sysctl.d/99-osm-network.conf`).

**Spec:** `docs/superpowers/specs/2026-08-28-network-and-socket-subsystem-tuning-design.md`

## Global Constraints

- Configuration drop-in path: `/etc/sysctl.d/99-osm-network.conf`
- Congestion control: `bbr` default with fallback to `cubic`
- Queueing discipline: `fq_codel`
- Fast Open: `3` (client + server)
- Non-interactive privileged execution: Use passwordless or `sudo -S` via `.env`
- Zero-Trust safety matrix: Non-destructive file writes with atomic snapshot tracking

---

### Task 1: Network Sysctl Configuration Generator & Audit Subsystem

**Files:**
- Modify: `os_manager/commands/tune.py:40-50, 880-920`
- Test: `tests/test_tune_network.py`

**Interfaces:**
- Produces: `SYSCTL_NETWORK_PATH: str`, `generate_network_sysctl_config(congestion_control: str = "bbr", qdisc: str = "fq_codel", fastopen: int = 3, somaxconn: int = 8192) -> str`, `audit_network_subsystem() -> dict[str, Any]`

- [ ] **Step 1: Write unit tests for generator and audit functions**

Write `tests/test_tune_network.py` asserting default configuration generation, customized parameters, structure of `audit_network_subsystem()`, and mocked sysctl reads.

- [ ] **Step 2: Run test to verify failure/missing implementation**

Run: `.venv/bin/pytest tests/test_tune_network.py` or `python3 -m unittest tests/test_tune_network.py`
Expected: FAIL if generator or audit functions are not yet exposed or incomplete.

- [ ] **Step 3: Implement `SYSCTL_NETWORK_PATH`, `generate_network_sysctl_config`, and `audit_network_subsystem` in `os_manager/commands/tune.py`**

```python
SYSCTL_NETWORK_PATH = "/etc/sysctl.d/99-osm-network.conf"

def generate_network_sysctl_config(
    congestion_control: str = "bbr",
    qdisc: str = "fq_codel",
    fastopen: int = 3,
    somaxconn: int = 8192,
) -> str:
    """Generate sysctl configuration for high-throughput, low-latency network stack."""
    return (
        "# /etc/sysctl.d/99-osm-network.conf - Managed by os-manager\n"
        f"net.core.default_qdisc = {qdisc}\n"
        f"net.ipv4.tcp_congestion_control = {congestion_control}\n"
        f"net.ipv4.tcp_fastopen = {fastopen}\n"
        "net.ipv4.tcp_slow_start_after_idle = 0\n"
        f"net.core.somaxconn = {somaxconn}\n"
        f"net.ipv4.tcp_max_syn_backlog = {somaxconn}\n"
        "net.ipv4.tcp_tw_reuse = 1\n"
        "net.ipv4.tcp_fin_timeout = 15\n"
        "net.ipv4.tcp_notsent_lowat = 16384\n"
    )

def audit_network_subsystem() -> dict[str, Any]:
    """Inspect active kernel network parameters and drop-in configuration status."""
    return {
        "congestion_control": _read_sysctl("net.ipv4.tcp_congestion_control"),
        "default_qdisc": _read_sysctl("net.core.default_qdisc"),
        "tcp_fastopen": _read_sysctl("net.ipv4.tcp_fastopen"),
        "slow_start_after_idle": _read_sysctl("net.ipv4.tcp_slow_start_after_idle"),
        "somaxconn": _read_sysctl("net.core.somaxconn"),
        "tcp_max_syn_backlog": _read_sysctl("net.ipv4.tcp_max_syn_backlog"),
        "tcp_tw_reuse": _read_sysctl("net.ipv4.tcp_tw_reuse"),
        "tcp_fin_timeout": _read_sysctl("net.ipv4.tcp_fin_timeout"),
        "tcp_notsent_lowat": _read_sysctl("net.ipv4.tcp_notsent_lowat"),
        "network_dropin_present": Path(SYSCTL_NETWORK_PATH).is_file(),
    }
```

- [ ] **Step 4: Run unit tests to verify pass**

Run: `python3 -m unittest tests/test_tune_network.py`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit changes**

```bash
git add os_manager/commands/tune.py tests/test_tune_network.py
git commit -m "feat(network): implement sysctl config generator and network audit subsystem"
```

---

### Task 2: Master Telemetry, Snapshot Rollback & System Tuning Integration

**Files:**
- Modify: `os_manager/commands/tune.py:1080-1175, 1480-1550`
- Test: `tests/test_tune_system.py`, `tests/test_tune_revert.py`

**Interfaces:**
- Consumes: `SYSCTL_NETWORK_PATH`, `generate_network_sysctl_config()`, `audit_network_subsystem()`
- Modifies: `collect_tune_telemetry()`, `apply_system_tuning()`, `create_system_snapshot()`

- [ ] **Step 1: Write integration tests for network in master telemetry and snapshot rollback**

Add assertions in `tests/test_tune_system.py` verifying that `collect_tune_telemetry()` returns `subsystems.network` and `apply_system_tuning(dry_run=True)` includes `SYSCTL_NETWORK_PATH`.

- [ ] **Step 2: Run test to verify failure**

Run: `python3 -m unittest tests/test_tune_system.py`
Expected: FAIL if `subsystems.network` is missing from telemetry.

- [ ] **Step 3: Update `collect_tune_telemetry`, `apply_system_tuning`, and snapshot handlers**

1. In `collect_tune_telemetry()`, populate `subsystems["network"] = audit_network_subsystem()`.
2. In `apply_system_tuning()`, add `SYSCTL_NETWORK_PATH` to the snapshot targets.
3. Write `generate_network_sysctl_config()` to `SYSCTL_NETWORK_PATH` upon `apply_system_tuning(dry_run=False)`.

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m unittest tests/test_tune_system.py tests/test_tune_revert.py`
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add os_manager/commands/tune.py tests/test_tune_system.py
git commit -m "feat(network): integrate network subsystem into master telemetry and system tuning"
```

---

### Task 3: CLI Routing & Subcommand Execution (`osm tune network`)

**Files:**
- Modify: `os_manager/commands/tune.py:1950-2050`, `os_manager/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- CLI: `osm tune network [--apply] [--dry-run] [--json]`

- [ ] **Step 1: Write CLI routing tests for `osm tune network`**

In `tests/test_cli.py`, add tests verifying:
- `osm tune network` executes audit mode (returns exit code 0).
- `osm tune network --apply --dry-run` prints planned network sysctl changes.
- `osm tune network --json` outputs valid JSON with network audit keys.

- [ ] **Step 2: Run CLI tests to verify failure**

Run: `python3 -m unittest tests/test_cli.py`
Expected: FAIL if `network` subaction is not handled in `tune.py` dispatcher.

- [ ] **Step 3: Implement `tune network` CLI handler**

In `os_manager/commands/tune.py`, add handler block for `parsed_args.subaction == "network"`:
- Support `--apply`, `--dry-run`, and `--json`.
- In audit mode, display formatted table/list of `net.ipv4.tcp_congestion_control`, `net.core.default_qdisc`, `tcp_fastopen`, etc.

- [ ] **Step 4: Run CLI unit tests and harness test suite**

Run: `python3 -m unittest tests/test_cli.py tests/test_tune_network.py`
Run: `./tests/test_harness.sh`
Expected: All tests pass.

- [ ] **Step 5: Commit changes**

```bash
git add os_manager/commands/tune.py os_manager/cli.py tests/test_cli.py
git commit -m "feat(cli): add osm tune network subcommand with audit and apply modes"
```
