"""os_manager/memory/psi_daemon.py - Autonomous PSI Feedback & zRAM Compaction Subsystem."""

import glob
import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

PsiSubsystem = Literal["cpu", "memory", "io"]
MitigationTier = Literal["none", "tier1_compact", "tier2_mglru_sync", "tier3_throttle_drop"]

PROC_PRESSURE_DIR = Path("/proc/pressure")
PRESSURE_FILES = {
    "cpu": PROC_PRESSURE_DIR / "cpu",
    "memory": PROC_PRESSURE_DIR / "memory",
    "io": PROC_PRESSURE_DIR / "io",
}


@dataclass
class PsiReading:
    """Parsed PSI stall metrics for a single pressure category (some or full)."""
    avg10: float = 0.0
    avg60: float = 0.0
    avg300: float = 0.0
    total: int = 0


@dataclass
class PsiMetrics:
    """Aggregated snapshot of all system pressure stall readings."""
    cpu_some: PsiReading
    memory_some: PsiReading
    memory_full: PsiReading
    io_some: PsiReading
    io_full: PsiReading
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class PsiThresholds:
    """Configurable trigger thresholds and cooldown windows for autonomous mitigations."""
    tier1_memory_some_avg10: float = 10.0
    tier1_memory_some_avg60: float = 5.0
    tier2_memory_some_avg10: float = 25.0
    tier2_memory_full_avg10: float = 10.0
    tier3_memory_full_avg10: float = 40.0
    cooldown_seconds: int = 20


def parse_psi_line(line: str) -> tuple[str, PsiReading] | None:
    """Parse a single line from /proc/pressure/{cpu,memory,io}."""
    line = line.strip()
    if not line:
        return None
    match = re.match(
        r"^(some|full)\s+avg10=([\d\.]+)\s+avg60=([\d\.]+)\s+avg300=([\d\.]+)\s+total=(\d+)",
        line,
    )
    if not match:
        return None
    prefix = match.group(1)
    reading = PsiReading(
        avg10=float(match.group(2)),
        avg60=float(match.group(3)),
        avg300=float(match.group(4)),
        total=int(match.group(5)),
    )
    return prefix, reading


def parse_psi_file(path: str | Path) -> dict[str, PsiReading]:
    """Parse a pressure file into a dictionary mapping 'some' and 'full' to PsiReading."""
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        content = p.read_text(encoding="utf-8")
        readings: dict[str, PsiReading] = {}
        for line in content.splitlines():
            res = parse_psi_line(line)
            if res:
                prefix, reading = res
                readings[prefix] = reading
        return readings
    except Exception:
        return {}


def collect_psi_metrics() -> PsiMetrics | None:
    """Collect current snapshot of all system PSI metrics."""
    if not PRESSURE_FILES["memory"].is_file():
        return None

    cpu_readings = parse_psi_file(PRESSURE_FILES["cpu"])
    mem_readings = parse_psi_file(PRESSURE_FILES["memory"])
    io_readings = parse_psi_file(PRESSURE_FILES["io"])

    return PsiMetrics(
        cpu_some=cpu_readings.get("some", PsiReading()),
        memory_some=mem_readings.get("some", PsiReading()),
        memory_full=mem_readings.get("full", PsiReading()),
        io_some=io_readings.get("some", PsiReading()),
        io_full=io_readings.get("full", PsiReading()),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


PSI_LOG_FILE = Path("backups/logs/psi_events.jsonl")


def _run_privileged(cmd: list[str], input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    """Execute privileged command non-interactively via sudo_exec.sh or sudo pipe."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    sudo_wrapper = repo_root / "scripts" / "sudo_exec.sh"

    if os.geteuid() == 0:
        return subprocess.run(cmd, input=input_text, capture_output=True, text=True, check=False)

    if sudo_wrapper.is_file() and os.access(sudo_wrapper, os.X_OK):
        full_cmd = [str(sudo_wrapper)] + cmd
        return subprocess.run(full_cmd, input=input_text, capture_output=True, text=True, check=False)

    env_path = repo_root / ".env"
    if not env_path.is_file():
        env_path = Path.cwd() / ".env"

    if env_path.is_file():
        joined_cmd = " ".join(f"'{c}'" for c in cmd)
        pipe_cmd = f"grep -E '^SUDO_PASSWORD=' '{env_path}' | cut -d '=' -f2- | sudo -S {joined_cmd}"
        return subprocess.run(pipe_cmd, shell=True, input=input_text, capture_output=True, text=True, check=False)

    return subprocess.run(["sudo", "-n"] + cmd, input=input_text, capture_output=True, text=True, check=False)


def _write_privileged_sysfs(target_path: str, value: str) -> bool:
    """Write value to sysfs or procfs securely using non-interactive sudo if needed."""
    p = Path(target_path)
    try:
        if os.geteuid() == 0:
            p.write_text(f"{value}\n", encoding="utf-8")
            return True

        res = _run_privileged(["tee", target_path], input_text=f"{value}\n")
        return res.returncode == 0
    except Exception:
        return False


def _log_psi_event(tier: str, reason: str, metrics: PsiMetrics | None = None) -> None:
    """Log critical memory pressure mitigation event to audit file."""
    try:
        PSI_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tier": tier,
            "reason": reason,
            "metrics": asdict(metrics) if metrics else {},
        }
        with open(PSI_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass


def compact_zram_devices() -> list[str]:
    """Trigger memory compaction across all active zRAM devices."""
    compacted: list[str] = []
    targets = glob.glob("/sys/block/zram*/compact")
    for target in targets:
        if _write_privileged_sysfs(target, "1"):
            compacted.append(target)
    return compacted


def trigger_mglru_kick() -> bool:
    """Re-enable MGLRU page aging and request dirty page writeback sync."""
    mglru_target = "/sys/kernel/mm/lru_gen/enabled"
    _write_privileged_sysfs(mglru_target, "1")
    try:
        os.sync()
    except Exception:
        pass
    return True


def trigger_critical_cache_drop(reason: str = "critical stall", metrics: PsiMetrics | None = None) -> bool:
    """Execute emergency page cache reclaim and record audit event."""
    _log_psi_event("tier3_throttle_drop", reason, metrics)
    return _write_privileged_sysfs("/proc/sys/vm/drop_caches", "1")


class StagedMitigationController:
    """3-Tier autonomous memory pressure mitigation engine with cooldown debouncing."""

    def __init__(self, thresholds: PsiThresholds | None = None):
        self.thresholds = thresholds or PsiThresholds()
        self.last_mitigation_time: float = 0.0
        self.last_mitigation_tier: MitigationTier = "none"
        self.mitigation_count: int = 0

    def evaluate_and_mitigate(self, metrics: PsiMetrics) -> dict[str, Any]:
        """Evaluate current PSI metrics against thresholds and trigger appropriate mitigation tier."""
        now = time.monotonic()
        time_since_last = now - self.last_mitigation_time
        in_cooldown = time_since_last < self.thresholds.cooldown_seconds

        # Determine target tier
        target_tier: MitigationTier = "none"
        reason = "pressure_normal"

        if metrics.memory_full.avg10 >= self.thresholds.tier3_memory_full_avg10:
            target_tier = "tier3_throttle_drop"
            reason = f"memory.full.avg10={metrics.memory_full.avg10:.2f} >= {self.thresholds.tier3_memory_full_avg10}"
        elif (
            metrics.memory_some.avg10 >= self.thresholds.tier2_memory_some_avg10
            or metrics.memory_full.avg10 >= self.thresholds.tier2_memory_full_avg10
        ):
            target_tier = "tier2_mglru_sync"
            reason = f"memory.some.avg10={metrics.memory_some.avg10:.2f} or memory.full.avg10={metrics.memory_full.avg10:.2f}"
        elif (
            metrics.memory_some.avg10 >= self.thresholds.tier1_memory_some_avg10
            or metrics.memory_some.avg60 >= self.thresholds.tier1_memory_some_avg60
        ):
            target_tier = "tier1_compact"
            reason = f"memory.some.avg10={metrics.memory_some.avg10:.2f} or memory.some.avg60={metrics.memory_some.avg60:.2f}"

        if target_tier == "none":
            return {
                "mitigated": False,
                "tier": "none",
                "reason": reason,
                "cooldown_active": in_cooldown,
                "cooldown_remaining": max(0.0, self.thresholds.cooldown_seconds - time_since_last),
            }

        if in_cooldown:
            return {
                "mitigated": False,
                "tier": target_tier,
                "reason": "cooldown_suppressed",
                "cooldown_active": True,
                "cooldown_remaining": max(0.0, self.thresholds.cooldown_seconds - time_since_last),
            }

        # Execute mitigation
        compacted: list[str] = []
        if target_tier in ("tier1_compact", "tier2_mglru_sync", "tier3_throttle_drop"):
            compacted = compact_zram_devices()

        if target_tier in ("tier2_mglru_sync", "tier3_throttle_drop"):
            trigger_mglru_kick()

        if target_tier == "tier3_throttle_drop":
            trigger_critical_cache_drop(reason=reason, metrics=metrics)

        self.last_mitigation_time = now
        self.last_mitigation_tier = target_tier
        self.mitigation_count += 1

        return {
            "mitigated": True,
            "tier": target_tier,
            "reason": reason,
            "compacted_devices": compacted,
            "cooldown_active": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


SYSTEMD_PSI_UNIT_PATH = "/etc/systemd/system/osm-psi.service"


def generate_psi_systemd_unit() -> str:
    """Generate systemd unit file content for osm-psi background daemon."""
    return """# /etc/systemd/system/osm-psi.service - Managed by os-manager
[Unit]
Description=os-manager Autonomous PSI Memory Feedback & zRAM Compaction Daemon
Documentation=https://github.com/0xrizz/os-manager
After=systemd-modules-load.service zramswap.service

[Service]
Type=simple
ExecStart=/usr/local/bin/osm psi daemon --run
Restart=always
RestartSec=5s
Nice=-5
MemoryHigh=64M
MemoryMax=128M

[Install]
WantedBy=multi-user.target
"""


def manage_psi_daemon(action: str) -> dict[str, Any]:
    """Control osm-psi daemon lifecycle: status, start, stop, enable, disable."""
    unit_installed = Path(SYSTEMD_PSI_UNIT_PATH).is_file()

    if action == "status":
        active = False
        enabled = False
        try:
            res_act = subprocess.run(["systemctl", "is-active", "osm-psi.service"], capture_output=True, text=True, check=False)
            active = res_act.stdout.strip() == "active"
            res_en = subprocess.run(["systemctl", "is-enabled", "osm-psi.service"], capture_output=True, text=True, check=False)
            enabled = res_en.stdout.strip() == "enabled"
        except Exception:
            pass
        return {
            "installed": unit_installed,
            "active": active,
            "enabled": enabled,
            "unit_path": SYSTEMD_PSI_UNIT_PATH,
        }

    if action == "start":
        unit_content = generate_psi_systemd_unit()
        _write_privileged_sysfs(SYSTEMD_PSI_UNIT_PATH, unit_content)
        _run_privileged(["systemctl", "daemon-reload"])
        res = _run_privileged(["systemctl", "restart", "osm-psi.service"])
        return {"success": res.returncode == 0, "action": "start", "error": res.stderr}

    if action == "stop":
        res = _run_privileged(["systemctl", "stop", "osm-psi.service"])
        return {"success": res.returncode == 0, "action": "stop", "error": res.stderr}

    if action == "enable":
        unit_content = generate_psi_systemd_unit()
        _write_privileged_sysfs(SYSTEMD_PSI_UNIT_PATH, unit_content)
        _run_privileged(["systemctl", "daemon-reload"])
        res = _run_privileged(["systemctl", "enable", "--now", "osm-psi.service"])
        return {"success": res.returncode == 0, "action": "enable", "error": res.stderr}

    if action == "disable":
        res = _run_privileged(["systemctl", "disable", "--now", "osm-psi.service"])
        return {"success": res.returncode == 0, "action": "disable", "error": res.stderr}

    return {"success": False, "error": f"Unknown daemon action '{action}'"}


def audit_psi_telemetry() -> dict[str, Any]:
    """Collect comprehensive telemetry for PSI support, daemon status, and live pressure."""
    metrics = collect_psi_metrics()
    supported = metrics is not None
    daemon_status = manage_psi_daemon("status")
    zram_devices = glob.glob("/sys/block/zram*/compact")

    telemetry: dict[str, Any] = {
        "supported": supported,
        "daemon_installed": daemon_status.get("installed", False),
        "daemon_active": daemon_status.get("active", False),
        "zram_devices": zram_devices,
    }

    if metrics:
        telemetry["timestamp"] = metrics.timestamp
        telemetry["cpu"] = {
            "some_avg10": metrics.cpu_some.avg10,
            "some_avg60": metrics.cpu_some.avg60,
            "some_avg300": metrics.cpu_some.avg300,
        }
        telemetry["memory"] = {
            "some_avg10": metrics.memory_some.avg10,
            "some_avg60": metrics.memory_some.avg60,
            "some_avg300": metrics.memory_some.avg300,
            "full_avg10": metrics.memory_full.avg10,
            "full_avg60": metrics.memory_full.avg60,
            "full_avg300": metrics.memory_full.avg300,
        }
        telemetry["io"] = {
            "some_avg10": metrics.io_some.avg10,
            "some_avg60": metrics.io_some.avg60,
            "some_avg300": metrics.io_some.avg300,
            "full_avg10": metrics.io_full.avg10,
            "full_avg60": metrics.io_full.avg60,
            "full_avg300": metrics.io_full.avg300,
        }
    return telemetry


class PsiMonitorEngine:
    """Monitoring and mitigation execution runner with timer-based polling loop."""

    def __init__(self, thresholds: PsiThresholds | None = None):
        self.controller = StagedMitigationController(thresholds=thresholds)

    def step(self) -> dict[str, Any] | None:
        """Execute one polling sample and evaluate mitigation."""
        metrics = collect_psi_metrics()
        if not metrics:
            return None
        mitigation_result = self.controller.evaluate_and_mitigate(metrics)
        return {
            "metrics": metrics,
            "mitigation": mitigation_result,
        }

    def run_daemon_loop(self, interval: float = 2.0) -> None:
        """Run continuous monitoring loop for daemon execution."""
        while True:
            try:
                self.step()
                time.sleep(interval)
            except KeyboardInterrupt:
                break
            except Exception:
                time.sleep(interval)

