# Network and Socket Subsystem Tuning Design Specification

- **Document ID**: `SPEC-2026-08-28-NET-TUNE-01`
- **Author**: os-manager Architecture & Performance Team
- **Date**: 2026-08-28
- **Status**: Approved for Implementation
- **Target Kernel**: Linux Kernel 6.6+ / 6.12 LTS on Debian 13 (Trixie) & WSL2 / Native Linux

---

## 1. Executive Summary & Problem Statement

Workstation, development, and AI agent workloads place intense, bursty demands on the Linux network stack. Frequent REST/JSON-RPC API calls to LLM gateways (such as Claude Code, Headroom, 9Router), high-concurrency Git repository pulls, and container registry downloads frequently suffer from:
1. **Bufferbloat & High Latency Jitter**: Default queueing disciplines (`pfifo_fast`) cause excessive packet buffering under high throughput, inflating round-trip time (RTT).
2. **Loss-Based Congestion Control Inefficiencies**: Default `cubic` assumes packet loss is caused by congestion, resulting in drastic throughput collapses on wireless (Wi-Fi 6/7) or virtualized (WSL2 vSwitch) interfaces.
3. **Connection Handshake Overhead**: Repeated three-way handshakes for short-lived HTTP/HTTPS API calls waste multiple round trips.
4. **TIME_WAIT Socket Exhaustion**: High-frequency API invocations quickly consume ephemeral port ranges and leave sockets lingering in `TIME_WAIT` for up to 60 seconds.

This specification introduces the **Network & Socket Subsystem Tuning** engine to `os-manager` via `osm tune network` and integrates network optimization into the unified `osm tune system` workflow.

---

## 2. Technical Architecture & Sysctl Parameters

The network engine manages an immutable, idempotent drop-in configuration at `/etc/sysctl.d/99-osm-network.conf` backed by atomic snapshot and rollback guarantees.

### 2.1 Sysctl Parameter Matrix

| Sysctl Key | Target Value | Baseline / Default | Architectural Rationale |
|---|---|---|---|
| `net.core.default_qdisc` | `fq_codel` | `pfifo_fast` | Fair Queueing with Controlled Delay prevents bufferbloat by keeping buffer queues short and prioritizing interactive/DNS/API traffic. |
| `net.ipv4.tcp_congestion_control` | `bbr` | `cubic` | Bottleneck Bandwidth and Round-trip propagation time (BBR) maximizes throughput while minimizing packet queueing at network bottlenecks. |
| `net.ipv4.tcp_fastopen` | `3` | `1` | Enables TCP Fast Open (TFO) for both incoming (server=1) and outgoing (client=2) connections (1 \| 2 = 3), enabling data exchange in the initial SYN packet. |
| `net.ipv4.tcp_slow_start_after_idle` | `0` | `1` | Prevents TCP congestion window from resetting to initial window size after socket idle periods, eliminating ramp-up latency on persistent API client sessions. |
| `net.core.somaxconn` | `8192` | `4096` | Increases the listen queue backlog for socket acceptance, avoiding dropped connections during bursty local AI / MCP server connection storms. |
| `net.ipv4.tcp_max_syn_backlog` | `8192` | `1024` | Expands incomplete connection queue capacity to handle simultaneous incoming TCP handshakes. |
| `net.ipv4.tcp_tw_reuse` | `1` | `2` / `0` | Allows safe reuse of `TIME_WAIT` sockets for outgoing connections when protocol timestamps confirm safety (RFC 1323). |
| `net.ipv4.tcp_fin_timeout` | `15` | `60` | Reduces the holding time for orphan sockets in `FIN-WAIT-2`, freeing kernel memory buffers 4x faster. |
| `net.ipv4.tcp_notsent_lowat` | `16384` | `4294967295` | Limits the amount of unsent buffered data in the socket write queue, minimizing local buffering latency on streaming responses. |

---

## 3. Module & Component Design

### 3.1 Constants & Paths in `os_manager/commands/tune.py`
```python
SYSCTL_NETWORK_PATH = "/etc/sysctl.d/99-osm-network.conf"
```

### 3.2 Generator Function
```python
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
```

### 3.3 Audit Subsystem Function
```python
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

### 3.4 Integration with Master Telemetry & Snapshots
1. **Snapshot Invariant**: `SYSCTL_NETWORK_PATH` is added to the target backup files in `create_system_snapshot()`.
2. **Master Telemetry**: `collect_tune_telemetry()` exposes `subsystems.network` with the dictionary returned by `audit_network_subsystem()`.
3. **Master System Tuning**: `apply_system_tuning()` writes `SYSCTL_NETWORK_PATH` and reloads sysctl via `sysctl --system`.

---

## 4. CLI Routing & User Interface

### 4.1 CLI Command Signature
- `osm tune network`: Audit current network sysctl settings.
- `osm tune network --apply [--dry-run]`: Generate and apply `/etc/sysctl.d/99-osm-network.conf`.
- `osm tune network --json`: Output machine-readable JSON structure for agent consumption.

---

## 5. Verification & Test Plan (TDD)

1. **Unit Test Suite (`tests/test_tune_network.py`)**:
   - `test_generate_network_sysctl_config`: Asserts exact sysctl lines are generated.
   - `test_audit_network_subsystem_mocked`: Asserts parsing of sysctl parameters and file presence detection.
   - `test_audit_network_subsystem_defaults`: Asserts fallback behavior when sysctl reads fail.
2. **CLI & System Integration (`tests/test_cli.py`, `tests/test_tune_system.py`)**:
   - Verify `osm tune network` and `osm tune network --apply` execute with status 0.
   - Verify telemetry contains `subsystems.network`.
3. **Snapshot Revert Verification (`tests/test_tune_revert.py`)**:
   - Ensure snapshots back up and restore `/etc/sysctl.d/99-osm-network.conf` cleanly.
