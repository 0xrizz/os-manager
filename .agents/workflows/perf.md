# /perf: System Performance & I/O Benchmark Command

Benchmark disk throughput and compare I/O latency across native Linux ext4 and Windows 9P mounts.

## Invocation
```bash
${PROJECT_DIR:-.}/scripts/perf_tune.sh "$@"
```

## Description
Executes storage performance benchmarks:
- Writes and reads test blocks to measure throughput
- Compares native ext4 (`${HOME}/`) against Windows 9P mounts (`/mnt/c/`, `/mnt/d/`)
- Measures operations latency and provides optimization guidance

## Flags & Arguments
- *(none)*: Standard 100MB benchmark
- `--quick`: Faster 20MB benchmark sample
- `--json`: Outputs structured JSON telemetry for programmatic profiling
