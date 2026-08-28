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


def _write_privileged_sysfs(target_path: str, value: str) -> bool:
    """Write value to sysfs or procfs securely using non-interactive sudo if needed."""
    p = Path(target_path)
    try:
        if os.geteuid() == 0:
            p.write_text(f"{value}\n", encoding="utf-8")
            return True

        # Non-interactive sudo pipe
        cmd = f"echo '{value}' | sudo -S tee '{target_path}'"
        env_path = Path.cwd() / ".env"
        if env_path.is_file():
            res = subprocess.run(
                f"grep -E '^SUDO_PASSWORD=' '{env_path}' | cut -d '=' -f2- | {cmd}",
                shell=True,
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            res = subprocess.run(["sudo", "-n", "tee", target_path], input=f"{value}\n", text=True, capture_output=True, check=False)
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
