#!/usr/bin/env bash
# scripts/perf_tune.sh - Filesystem I/O performance benchmark utility for WSL2
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

FORMAT="text"
BLOCK_COUNT=100
BLOCK_SIZE="1M"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --json)
            FORMAT="json"
            shift
            ;;
        --quick)
            BLOCK_COUNT=20
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--json] [--quick]"
            echo "  --json   Output results in JSON format"
            echo "  --quick  Run a smaller 20MB benchmark sample"
            exit 0
            ;;
        *)
            echo "Unknown flag: $1" >&2
            exit 1
            ;;
    esac
done

benchmark_path() {
    local target_dir="$1"
    local label="$2"
    local test_file="${target_dir}/.os_manager_io_test.tmp"

    if [ ! -d "${target_dir}" ] || [ ! -w "${target_dir}" ]; then
        echo "{\"label\":\"${label}\",\"path\":\"${target_dir}\",\"status\":\"unwritable\"}"
        return 0
    fi

    # Measure write performance
    local write_out
    write_out=$(dd if=/dev/zero of="${test_file}" bs="${BLOCK_SIZE}" count="${BLOCK_COUNT}" conv=fdatasync 2>&1)
    local write_speed
    write_speed=$(echo "${write_out}" | awk '/bytes/{print $(NF-1), $NF}')

    # Measure read performance
    local read_out
    read_out=$(dd if="${test_file}" of=/dev/null bs="${BLOCK_SIZE}" count="${BLOCK_COUNT}" 2>&1)
    local read_speed
    read_speed=$(echo "${read_out}" | awk '/bytes/{print $(NF-1), $NF}')

    rm -f "${test_file}"

    if [ "${FORMAT}" = "json" ]; then
        echo "{\"label\":\"${label}\",\"path\":\"${target_dir}\",\"write_speed\":\"${write_speed}\",\"read_speed\":\"${read_speed}\",\"status\":\"ok\"}"
    else
        echo "[$label] Path: ${target_dir}"
        echo "  Write Speed: ${write_speed}"
        echo "  Read Speed:  ${read_speed}"
    fi
}

if [ "${FORMAT}" = "json" ]; then
    echo "{"
    echo "  \"timestamp\": \"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\","
    echo "  \"benchmarks\": ["
    echo "    $(benchmark_path "${WORKSPACE_ROOT}" "Native EXT4 (Workspace)"),"
    echo "    $(benchmark_path "/tmp" "Native EXT4 (/tmp)"),"
    echo "    $(benchmark_path "/mnt/d/wsl_backup" "Windows D: 9P Mount")"
    echo "  ]"
    echo "}"
else
    echo "=================================================="
    echo "      os-manager WSL2 I/O Latency Benchmark       "
    echo "=================================================="
    benchmark_path "${WORKSPACE_ROOT}" "Native EXT4 (Workspace)"
    echo "--------------------------------------------------"
    benchmark_path "/tmp" "Native EXT4 (/tmp)"
    echo "--------------------------------------------------"
    benchmark_path "/mnt/d/wsl_backup" "Windows D: 9P Mount"
    echo "=================================================="
fi
