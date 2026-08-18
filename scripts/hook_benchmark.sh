#!/usr/bin/env bash
# scripts/hook_benchmark.sh - Latency benchmark reporting CLI for Claude Code lifecycle hooks
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUDIT_LOG="${WORKSPACE_ROOT}/backups/logs/harness_audit.jsonl"
SAMPLE_LIMIT=500
FILTER_HOOK=""
FORMAT="table"
ASSERT_P99=false
TAIL_MODE=false

usage() {
    cat <<USAGETEXT
Usage: $0 [OPTIONS]

Options:
  --samples <N>     Analyze the last N events (default: 500)
  --hook <name>     Filter statistics by hook name
  --log <path>      Override path to harness_audit.jsonl
  --json            Output statistics in JSON format
  --summary         Print terminal summary table (default)
  --tail <N>        Print the last N raw trace events
  --assert-p99      Exit with code 1 if any hook P99 exceeds 100ms
  --help, -h        Display this help message
USAGETEXT
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --samples)
            SAMPLE_LIMIT="$2"
            shift 2
            ;;
        --hook)
            FILTER_HOOK="$2"
            shift 2
            ;;
        --log)
            AUDIT_LOG="$2"
            shift 2
            ;;
        --json)
            FORMAT="json"
            shift
            ;;
        --summary)
            FORMAT="table"
            shift
            ;;
        --tail)
            TAIL_MODE=true
            SAMPLE_LIMIT="${2:-10}"
            shift 2
            ;;
        --assert-p99)
            ASSERT_P99=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

if [ ! -f "${AUDIT_LOG}" ]; then
    if [ "${FORMAT}" = "json" ]; then
        echo "{}"
    else
        echo "No audit telemetry found at ${AUDIT_LOG}"
    fi
    exit 0
fi

if [ "${TAIL_MODE}" = true ]; then
    tail -n "${SAMPLE_LIMIT}" "${AUDIT_LOG}"
    exit 0
fi

# Process log data using Python for precision percentile calculation
python3 -c "
import json, sys, os

log_file = '${AUDIT_LOG}'
sample_limit = int('${SAMPLE_LIMIT}')
filter_hook = '${FILTER_HOOK}'
format_type = '${FORMAT}'
assert_p99 = ('${ASSERT_P99}' == 'true')

records = []
if os.path.exists(log_file):
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                if 'hook_name' in data and 'duration_ms' in data:
                    records.append(data)
            except Exception:
                continue

if sample_limit > 0 and len(records) > sample_limit:
    records = records[-sample_limit:]

grouped = {}
for r in records:
    hook = r['hook_name']
    if filter_hook and hook != filter_hook:
        continue
    grouped.setdefault(hook, []).append(float(r['duration_ms']))

stats = {}
p99_violated = False

for hook, durations in sorted(grouped.items()):
    durations.sort()
    count = len(durations)
    if count == 0:
        continue
    min_val = durations[0]
    max_val = durations[-1]
    mean_val = sum(durations) / count
    p50 = durations[int(count * 0.50)]
    p95 = durations[min(count - 1, int(count * 0.95))]
    p99 = durations[min(count - 1, int(count * 0.99))]

    if p99 > 100.0:
        p99_violated = True

    stats[hook] = {
        'count': count,
        'min_ms': round(min_val, 2),
        'mean_ms': round(mean_val, 2),
        'p50_ms': round(p50, 2),
        'p95_ms': round(p95, 2),
        'p99_ms': round(p99, 2),
        'max_ms': round(max_val, 2),
        'status': 'FAIL (>100ms)' if p99 > 100.0 else 'OK (<100ms)'
    }

if format_type == 'json':
    print(json.dumps(stats, indent=2))
else:
    print('=' * 80)
    print('                    CLAUDE CODE HOOK LATENCY BENCHMARK REPORT')
    print('=' * 80)
    print(f'Sample Window: Last {len(records)} events from {log_file}\n')
    header = f'{\"HOOK NAME\":<20} {\"COUNT\":>6} {\"MIN (ms)\":>9} {\"P50 (ms)\":>9} {\"P95 (ms)\":>9} {\"P99 (ms)\":>9} {\"MAX (ms)\":>9}   {\"STATUS\"}'
    print(header)
    print('-' * 80)
    for hook, s in stats.items():
        print(f\"{hook:<20} {s['count']:>6} {s['min_ms']:>9.2f} {s['p50_ms']:>9.2f} {s['p95_ms']:>9.2f} {s['p99_ms']:>9.2f} {s['max_ms']:>9.2f}   {s['status']}\")
    print('=' * 80)
    verdict = 'FAIL (P99 latency threshold violated)' if p99_violated else 'PASS (100% of hooks meet the sub-100ms P99 requirement)'
    print(f'OVERALL VERDICT: {verdict}')
    print('=' * 80)

if assert_p99 and p99_violated:
    sys.exit(1)
"
