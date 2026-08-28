"""os_manager/memory/psi_daemon.py - Autonomous PSI Feedback & zRAM Compaction Subsystem."""

import os
import re
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
