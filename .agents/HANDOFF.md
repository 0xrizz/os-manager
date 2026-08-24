# CHECKPOINT HANDOFF: zRAM 100% (8GB) Scaling & Subsystem Synchronization

**Status:** PLAN READY FOR SUBAGENT-DRIVEN DEVELOPMENT (SDD)  
**Date:** 2026-08-24  
**Branch:** `main`  
**Target Environment:** Bare-Metal Debian GNU/Linux 13 (Trixie), Linux Kernel 6.12.101+, Lenovo IdeaPad 3 (81WD) with Intel Core i5-1035G1 + NVIDIA GeForce MX330 + 8GB RAM + NVMe SSD  
**Design Specification:** [`docs/superpowers/specs/2026-08-24-adaptive-kernel-system-optimization-design.md`](file:///home/rizz/dev/os-manager/docs/superpowers/specs/2026-08-24-adaptive-kernel-system-optimization-design.md)  
**Implementation Plan:** [`docs/superpowers/plans/2026-08-24-zram-100-percent-scaling-and-sync.md`](file:///home/rizz/dev/os-manager/docs/superpowers/plans/2026-08-24-zram-100-percent-scaling-and-sync.md)  

---

## 1. Executive Summary & Context

The Adaptive Kernel & System Optimization Suite (Tasks 1–8) has been completed and verified with 100% test pass rate (234/234 tests passing).  
The user has approved scaling the compressed in-memory swap (**zRAM**) from the conservative 50% (~3.75 GiB) to **100% of RAM (~7.5 GiB / 8192 MB)** with `zstd` multi-stream compression to support heavy developer multitasking (Antigravity IDE, browser multi-tabbing, background 9router agent, headroom, and Spotify).

An implementation plan with 3 bite-sized TDD tasks has been authored and committed to [`docs/superpowers/plans/2026-08-24-zram-100-percent-scaling-and-sync.md`](file:///home/rizz/dev/os-manager/docs/superpowers/plans/2026-08-24-zram-100-percent-scaling-and-sync.md).

---

## 2. Scope of Tasks to Execute in Next Session

### Task 1: Codebase Template Synchronization
- **Files:** `os_manager/commands/hsi.py`, `scripts/hsi-harden.sh`, `tests/test_hsi_hardening.py`
- **Actions:** Update `generate_zram_config` to default `ram_fraction="ram"`, update `scripts/hsi-harden.sh` template to `min(ram, 8192)`, update unit tests in `tests/test_hsi_hardening.py`.
- **TDD:** Verify red-green cycle in `pytest tests/test_hsi_hardening.py`.

### Task 2: Live Host zRAM Deployment & Systemd Reinitialization
- **Files:** `/etc/systemd/zram-generator.conf`
- **Actions:** Backup existing file, deploy `zram-size = min(ram, 8192)` with `zstd` and priority 100, execute `systemctl daemon-reload`, recycle swap (`swapoff /dev/zram0` -> restart `systemd-zram-setup@zram0.service` -> `swapon /dev/zram0`), restart `earlyoom.service`.
- **Verification:** Assert `/dev/zram0` shows ~7.5 GiB in `cat /proc/swaps` and `free -h`.

### Task 3: Full Telemetry Audit & End-to-End Verification
- **Actions:** Audit `osm tune all --json`, benchmark `osm perf all --quick`, run full test suite `.venv/bin/pytest tests/ -v` (234+ tests passing).
- **Handoff:** Update `.agents/HANDOFF.md` with final verification metrics.

---

## 3. Quick Execution Instructions for Continuing Agent

```bash
# 1. Initialize SDD Workspace:
bash .agents/skills/subagent-driven-development/scripts/init docs/superpowers/plans/2026-08-24-zram-100-percent-scaling-and-sync.md

# 2. Iterate Tasks 1..3 via SDD Loop:
# - Extract Brief: bash .agents/skills/subagent-driven-development/scripts/task-brief docs/superpowers/plans/2026-08-24-zram-100-percent-scaling-and-sync.md <N>
# - Dispatch Implementer (TypeName: "self")
# - Package Review: bash .agents/skills/subagent-driven-development/scripts/review-package docs/superpowers/plans/2026-08-24-zram-100-percent-scaling-and-sync.md <BASE> <HEAD>
# - Dispatch Reviewer (TypeName: "research")
# - Update ledger in .superpowers/sdd/.../progress.md

# 3. Final Verification:
.venv/bin/pytest tests/ -v
```

---

## 4. Current Baseline Verification
```text
- Git HEAD: b705d87 (main)
- Full pytest suite: 234 passed in 5.00s (100% passing)
- Zero-Data-Loss Invariant: /dev/nvme0n1p4 (/mnt/data) protected
- Non-Interactive Sudo: .env password streaming via `sudo -S`
```
