---
name: perf-tune
description: Use when measuring I/O latency between ext4 and 9P Windows mounts, running disk throughput benchmarks, or diagnosing filesystem performance bottlenecks
---

# Performance Tuning and I/O Benchmark Skill

Measures write and read throughput across native Linux ext4 partitions and Windows 9P mounts (`/mnt/c/`, `/mnt/d/`).

## Trigger Scenarios
- Investigating slow build times or package installation bottlenecks
- Comparing I/O latency between native ext4 (`${HOME}/`) and Windows host mounts
- Verifying storage performance before running intensive data or AI workflows

## Invocation
```bash
${CLAUDE_PROJECT_DIR}/scripts/perf_tune.sh [flags]
```

## Command Options
| Option | Description |
| :--- | :--- |
| *(none)* | Executes standard 100MB read and write benchmark |
| `--quick` | Runs faster 20MB benchmark sample |
| `--json` | Emits structured JSON results for automated profiling |

## Safety Classification
- **Tier 2 (Controlled System Operation)**: Non-destructive benchmark operating in workspace and temp directories.
