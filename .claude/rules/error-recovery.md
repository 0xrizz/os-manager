# Error Recovery & Auto-Healing Protocols

Operational protocols for responding to hook rejections, syntax verification failures, runtime exceptions, and tool degradation.

## 1. Hook Interruption Protocols (Exit Code 2)

Lifecycle hooks block execution and return Exit Code 2 with structured diagnostic output on `stderr`.

- **PreToolUse Guardrail Block (Tier 3 Invariants)**:
  - Read the invariant violation reason on `stderr`.
  - Do not retry the exact command verbatim.
  - Pivot to a safe, workspace-contained alternative or report the constraint to the user.
- **PostToolUse Quality Gate Block (Syntax Lint Failures)**:
  - Read the exact file path and line number reported on `stderr`.
  - Prioritize an immediate repair turn on the target file before running any other command.
  - Validate syntax against the specific tool reported (`bash -n`, `shellcheck`, `jq empty`, `python3 -m py_compile`).

## 2. Execution Failure Triage

When a command exits with a non-zero status outside of hook interruptions:

- **Missing CLI Dependencies**:
  - Verify binary availability via `which <command>` or `command -v <command>`.
  - If optional formatting tools (`shellcheck`, `shfmt`) are absent, fall back to core runtime validators (`bash -n`, `python3 -m py_compile`, `jq`).
- **Telemetry Inspection**:
  - Check `backups/logs/harness_errors.jsonl` for timestamped tool failure context when silent failures occur.
- **Circuit Breaker (Loop Prevention)**:
  - If a repair attempt fails twice on the same syntax or runtime defect, stop autonomous retries.
  - Read the full target file with `Read` to inspect surrounding context before making further edits.

## 3. Storage & Boundary Recovery

- **Unreachable Windows Mounts (`/mnt/c/`, `/mnt/d/`)**:
  - Verify mount state via `df -h` and `ls -ld /mnt/d`.
  - If `/mnt/d/` is unmounted or read-only during backup operations, fail fast with an actionable notification; do not write large backup tarballs to the native ext4 root partition without confirmation.
- **Path Canonicalization**:
  - Use absolute paths or resolve symbolic links via `realpath -m <path>` when working across workspace boundaries.
