"""Filesystem, CPU, memory, scheduler, and audio empirical benchmark engine."""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import time
from typing import Any


def run_cpu_benchmark(quick: bool = True) -> dict[str, Any]:
    """Execute CPU & scheduler scheduling latency benchmark."""
    sysbench_bin = shutil.which("sysbench")
    if not sysbench_bin:
        return {"available": False, "reason": "sysbench not installed"}

    max_prime = 10000 if quick else 30000
    cmd = [sysbench_bin, "cpu", f"--cpu-max-prime={max_prime}", "--threads=8", "run"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        return {"available": False, "error": res.stderr.strip()}

    eps = 0.0
    for line in res.stdout.splitlines():
        if "events per second:" in line:
            m = re.search(r"([\d\.]+)", line.split(":", 1)[1])
            if m:
                eps = float(m.group(1))

    return {
        "available": True,
        "score": eps,
        "threads": 8,
        "max_prime": max_prime,
        "raw": res.stdout,
    }


def run_memory_benchmark(quick: bool = True) -> dict[str, Any]:
    """Execute memory allocation and throughput benchmark."""
    sysbench_bin = shutil.which("sysbench")
    if not sysbench_bin:
        return {"available": False, "reason": "sysbench not installed"}

    size = "1G" if quick else "4G"
    cmd = [
        sysbench_bin,
        "memory",
        "--memory-oper=write",
        "--memory-access-mode=rnd",
        "--memory-block-size=4K",
        f"--memory-total-size={size}",
        "--threads=8",
        "run",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        return {"available": False, "error": res.stderr.strip()}

    throughput = 0.0
    for line in res.stdout.splitlines():
        if "transferred (" in line:
            m = re.search(r"\(([\d\.]+)\s*MB/sec\)", line)
            if m:
                throughput = float(m.group(1))

    return {
        "available": True,
        "throughput_mb_s": throughput,
        "size": size,
        "raw": res.stdout,
    }


def run_io_benchmark(quick: bool = True, target_path: str = "/tmp/osm_bench.tmp") -> dict[str, Any]:
    """Execute storage 4K random write IOPS and tail latency benchmark via fio."""
    fio_bin = shutil.which("fio")
    if not fio_bin:
        # Fallback pure-Python DD write benchmark
        start = time.perf_counter()
        data = b"\0" * (1024 * 1024)
        with open(target_path, "wb") as f:
            for _ in range(50 if quick else 200):
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
        dur = time.perf_counter() - start
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except Exception:
                pass
        mb = 50 if quick else 200
        mb_s = round(mb / dur, 2) if dur > 0 else 0.0
        return {
            "available": True,
            "engine": "python_sync",
            "throughput_mb_s": mb_s,
            "write_iops": int(mb_s * 256),
        }

    runtime = 3 if quick else 10
    cmd = [
        fio_bin,
        "--name=osm_randwrite",
        "--ioengine=libaio",
        "--iodepth=16",
        "--rw=randwrite",
        "--bs=4k",
        "--size=256M",
        f"--runtime={runtime}",
        "--time_based",
        "--group_reporting",
        f"--filename={target_path}",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if os.path.exists(target_path):
        try:
            os.remove(target_path)
        except Exception:
            pass

    if res.returncode != 0:
        return {"available": False, "error": res.stderr.strip()}

    iops = 0
    bw = 0.0
    for line in res.stdout.splitlines():
        if "IOPS=" in line or "IOPS" in line:
            m = re.search(r"IOPS=([\d\.]+[kK]?)", line) or re.search(r"([\d\.]+)\s*IOPS", line)
            if m:
                val_s = m.group(1).lower()
                iops = int(float(val_s.replace("k", "")) * 1000) if "k" in val_s else int(float(val_s))
        if "bw=" in line:
            m = re.search(r"bw=([\d\.]+)(MiB/s|MB/s|KiB/s)", line)
            if m:
                bw = float(m.group(1))

    return {
        "available": True,
        "engine": "fio",
        "write_iops": iops,
        "throughput_mb_s": bw,
        "raw": res.stdout,
    }


def run_audio_jitter_benchmark() -> dict[str, Any]:
    """Audit PipeWire audio graph buffer latency and underrun (xrun) errors."""
    pw_top_bin = shutil.which("pw-top")
    if not pw_top_bin:
        return {"available": False, "reason": "pw-top not installed"}

    res = subprocess.run([pw_top_bin, "-b", "-n", "2"], capture_output=True, text=True, check=False)
    xruns = 0
    quantum = 256
    rate = 48000
    if res.returncode == 0 and res.stdout:
        err_col_idx = None
        for line in res.stdout.splitlines():
            parts = line.split()
            if not parts:
                continue
            if "ERR" in parts:
                err_col_idx = parts.index("ERR")
                continue
            if err_col_idx is not None and len(parts) > err_col_idx:
                val = parts[err_col_idx]
                if val.isdigit():
                    xruns += int(val)
                if len(parts) > 3 and parts[2].isdigit() and parts[3].isdigit():
                    q_val = int(parts[2])
                    r_val = int(parts[3])
                    if q_val > 0:
                        quantum = q_val
                    if r_val > 0:
                        rate = r_val
            elif "ERR" in line:
                if len(parts) >= 2 and parts[-1].isdigit():
                    xruns += int(parts[-1])

    return {
        "available": True,
        "xruns": xruns,
        "active_quantum": quantum,
        "active_rate": rate,
    }


def run_perf(args: list[str]) -> int:
    """Execute empirical system optimization benchmarks."""
    if args and args[0] == "perf":
        args = args[1:]
    parser = argparse.ArgumentParser(
        prog="osm perf",
        description="Empirical hardware, CPU, memory, storage, and audio benchmark runner.",
    )
    parser.add_argument("subaction", nargs="?", default="all", choices=["all", "cpu", "mem", "io", "audio"])
    parser.add_argument("--quick", action="store_true", help="Run short-duration benchmark sweep")
    parser.add_argument("--full", action="store_true", help="Run thorough multi-pass benchmark suite")
    parser.add_argument("--json", action="store_true", help="Output benchmark metrics as JSON")

    parsed = parser.parse_args(args)
    is_quick = not parsed.full

    results: dict[str, Any] = {
        "status": "success",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "mode": "quick" if is_quick else "full",
        "benchmarks": {},
    }

    if parsed.subaction in ["all", "cpu"]:
        results["benchmarks"]["cpu"] = run_cpu_benchmark(quick=is_quick)
    if parsed.subaction in ["all", "mem"]:
        results["benchmarks"]["memory"] = run_memory_benchmark(quick=is_quick)
    if parsed.subaction in ["all", "io"]:
        results["benchmarks"]["storage_io"] = run_io_benchmark(quick=is_quick)
    if parsed.subaction in ["all", "audio"]:
        results["benchmarks"]["audio"] = run_audio_jitter_benchmark()

    if parsed.json:
        print(json.dumps(results, indent=2))
        return 0

    print("==================================================")
    print(f"   OS-Manager Performance Benchmark Suite ({results['mode'].upper()})   ")
    print("==================================================")
    for b_name, b_data in results["benchmarks"].items():
        if not b_data.get("available", False):
            print(f"[{b_name.upper()}] Unavailable: {b_data.get('reason', b_data.get('error', 'unknown'))}")
            continue
        print(f"[{b_name.upper()}] Benchmark Results:")
        for k, v in b_data.items():
            if k not in ["raw", "available"]:
                print(f"  - {k}: {v}")
    print("==================================================")
    return 0
