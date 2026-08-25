# Specification: Open-Source Transformation Roadmap & Zero-Trust Governance Architecture for OS-Manager

- **Date:** 2026-08-24
- **Scope:** Open-Source Decoupling, Zero-Trust AST Security, Dynamic HAL, Multi-Agent MCP, and Package Distribution
- **Status:** Proposed / Active Specification Baseline
- **Author:** Lead Systems Engineer & Open-Source Product Strategist
- **Supersedes:** 
  - `docs/superpowers/specs/2026-08-19-open-source-os-manager-specification.md` (Superseded: Initial packaging baseline replaced by universal AST guard, dynamic HAL, and declarative `.osm.toml` architecture).
  - `docs/superpowers/specs/2026-08-18-claude-harness-architecture.md` (Partially Superseded: Section on regex-based `PreToolUse` hooks replaced by Shell AST Parser & Bubblewrap Sandbox).

---

## 1. Executive Summary & Core Philosophy

`os-manager` is the autonomous AI governance harness, workstation performance optimizer, and multi-agent control plane for developer environments across Linux (Debian/Ubuntu/Arch/Fedora), WSL2 on Windows 11, and macOS.

While the initial version achieved a 4-tier security matrix and deterministic lifecycle hooks, an empirical audit revealed significant personal machine tight-coupling (Lenovo IdeaPad 3 81WD, Intel Ice Lake, SSSTC NVMe, Realtek ALC298 audio), regex-based security filters vulnerable to shell obfuscation/redirection bypasses, fragmented test infrastructure, and procedural configuration.

This specification outlines the comprehensive Open-Source Transformation Roadmap to transition `os-manager` into a portable, zero-config, community-ready framework while preserving its foundational pillars:
1. **Autonomous AI Governance Harness** (Deterministic lifecycle hooks & self-healing linting).
2. **Zero-Trust Host Security** (Shell AST validation & rootless Bubblewrap/Podman container sandboxing).
3. **Workstation Performance Tuning** (Dynamic block I/O scheduler, zRAM/swap tuning, CPU/power optimization).
4. **Multi-Agent Orchestration Protocol** (Standardized MCP server, Unix domain JSON-RPC broker, and SQLite state ledger).

---

## 2. Hasil Audit Empiris Codebase

### 2.1 Coupling Personal vs Kebutuhan Universal

| File Path & Line Reference | Elemen Hardcoded / Personal Invariant | Failure Mode pada Perangkat Lain | Abstraksi Solusi Universal |
|---|---|---|---|
| `scripts/tune_hardware.sh` (L5-9)<br>`os_manager/commands/tune.py` (L13-17) | `SYSFS_CONSERVATION_DEFAULT` & `SYSFS_FN_LOCK_DEFAULT` (`/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/...`) | Gagal eksekusi (exit code 1) pada vendor selain Lenovo (Dell, ASUS, ThinkPad, HP, macOS, Desktop). | `AbstractHardwareDriver` dengan DMI/sysfs vendor detection (`/sys/class/dmi/id/`). |
| `os_manager/commands/tune.py` (L593, L603)<br>`scripts/tune_system.sh` (L213-221) | `/sys/block/nvme0n1/queue/scheduler`<br>`/sys/block/nvme0n1/queue/nr_requests` | `FileNotFoundError` atau no-op pada SATA SSD (`/dev/sda`), multiple NVMe (`nvme1n1`), atau cloud VHD (`/dev/vda`). | Block device discovery dinamis (`findmnt / -no SOURCE` + iterasi `/sys/block/*/queue`). |
| `scripts/hsi-harden.sh` (L4-5, L20-21, L65-66) | Target Lenovo 81WD, `PROTECTED_PARTITION="/dev/nvme0n1p4"`, regex `/nvme0n1p4\|\/mnt\/data/` | Crash / data loss pada skema partisi non-standard; bypass proteksi jika disk menggunakan skema partisi berbeda. | Declarative disk protection config di `.osm.toml` (`security.protected_mounts`, `uuids`). |
| `scripts/upgrade_debian_trixie.sh` (L228, L466-467, L703) | `ROOT_PART="/dev/nvme0n1p2"`, `EFI_PART="/dev/nvme0n1p1"` | Menulis bootloader GRUB ke target disk yang salah pada sistem multi-drive atau non-NVMe. | Auto-detect ESP via `bootctl status` / `findmnt /boot/efi -no SOURCE`. |
| `scripts/migration/*` (All 11 scripts) | Partisi `p1`-`p6`, SSSTC CL1-4D512 512GB geometry, FAT32 `DEBIAN_SET` | Berbahaya jika dijalankan di mesin sembarang; berasumsi tata letak partisi Windows/Debian dual-boot tertentu. | Isolasi skrip migrasi legacy ke playbook opsional dengan flag `--profile legacy-lenovo`. |
| `AGENTS.md` (L9-18)<br>`.claude/settings.local.json` | Spesifikasi personal (Lenovo 81WD, ALC298, `/home/rizz`) | Hardcoded paths di local settings dan docs membocorkan username personal dan invariant host. | Template generation dinamis via `osm init` dengan dynamic `$HOME` dan runtime probing. |

### 2.2 Analisis Celah Keamanan pada `scripts/hooks/pre_tool_guard.sh`

Pola mitigasi saat ini mengandalkan evaluasi POSIX regex (`grep -qE` dan `[[ =~ ]]`) pada raw command string.

#### Kerentanan Pola Regex Eksisting:
1. **Shell Redirection Bypass**:
   - Aturan proteksi file (L45-60) hanya memvalidasi pemanggilan tool `Edit` dan `Write`. Eksekusi perintah bash seperti `cat payload > /etc/shadow` atau `tee -a /etc/passwd` melewati rule path invariant karena regex tool guard hanya memvalidasi `Edit|Write|Read`.
2. **Obfuscation & Dynamic Code Execution**:
   - Regex token matching (`\brm\s+-[rRfF]*\s+(/|...)`) tidak mendeteksi:
     - `eval "$(echo cm0gLXJmIC8= | base64 -d)"`
     - `export D=/; rm -rf $D`
     - `python3 -c 'import shutil; shutil.rmtree("/")'`
     - Concatenation: `r'm' -'r'f /`
3. **Fail-Open Sandboxing**:
   - Baris 85-89: Fallback Podman bersifat opsional. Jika Podman tidak terpasang, perintah berbahaya langsung diteruskan ke host OS tanpa isolasi (`exit 0`).

### 2.3 State Testing & Ketiadaan Konfigurasi Deklaratif

1. **Fragmentasi Pengujian**: 56 test suite (19 file Python `unittest` dan 37 shell script `tests/*.sh`). Belum ada unified test runner dengan virtualization mock (sysfs/DMI).
2. **Ketiadaan Konfigurasi Deklaratif**: Konfigurasi tersebar di script string generation (`tune.py:514-1375`), hardcoded script constants, dan environment variables. Tidak ada manifest `.osm.toml` tunggal.

---

## 3. 5 Pilar Peningkatan Strategis Open-Source

```text
 ══════════════════════════════════════════════════════════════════════════════════════════════════════
                                  OS-MANAGER CONTROL PLANE MATRIX                                     
 ══════════════════════════════════════════════════════════════════════════════════════════════════════
                                                   │
        ┌──────────────────┬───────────────────────┼───────────────────────┬──────────────────┐
        ▼                  ▼                       ▼                       ▼                  ▼
 ┌──────────────┐   ┌──────────────┐        ┌──────────────┐        ┌──────────────┐   ┌──────────────┐
 │   PILAR 1    │   │   PILAR 2    │        │   PILAR 3    │        │   PILAR 4    │   │   PILAR 5    │
 │  UNIVERSAL   │   │  NATIVE MCP  │        │ ZERO-TRUST   │        │ MULTI-AGENT  │   │ DECLARATIVE  │
 │ PROFILER/HAL │   │SERVER ENGINE │        │ AST & BWRAP  │        │ STATE LEDGER │   │ PACKAGING/DX │
 ├──────────────┤   ├──────────────┤        ├──────────────┤        ├──────────────┤   ├──────────────┤
 │•DMI / Sysfs  │   │•Model Context│        │•Shell AST    │        │•SQLite WAL   │   │•.osm.toml    │
 │ Dynamic Walk │   │ Protocol     │        │ Parser       │        │ Event Store  │   │ Config Spec  │
 │•Vendor Driver│   │•osm_safe_exec│        │ (bashlex)    │        │•Distributed  │   │•PyPI / Brew  │
 │ Registry     │   │•osm_telemetry│        │•Bubblewrap   │        │ Mutex Lock   │   │ AUR / Deb    │
 │ (Lenovo/Asus/│   │•osm_sandbox  │        │ Rootless     │        │•Handoff JSON │   │•Unified      │
 │  Dell/Apple) │   │•stdio / SSE  │        │ Jail Engine  │        │ Schema       │   │ Pytest Suite │
 └──────────────┘   └──────────────┘        └──────────────┘        └──────────────┘   └──────────────┘
```

### Pilar 1: Portabilitas & Universal Hardware Profiler (HAL)
- Mengganti static sysfs path dengan generic sysfs tree walker (`/sys/class/power_supply/*`, `/sys/devices/system/cpu/*`, `/sys/block/*`).
- Membangun `HardwareRegistry` berbasis DMI/SMBIOS vendor driver plugin:
  - `LenovoDriver` (`ideapad_acpi`, `thinkpad_acpi`)
  - `AsusDriver` (`asus_wmi`)
  - `DellDriver` (`dell_laptop`, `dell_smbios`)
  - `AppleDriver` (macOS `pmset`, `sysctl`)
  - `GenericLinuxDriver` (fallback standard ACPI `platform_profile`).

### Pilar 2: Native MCP (Model Context Protocol) Server Integration
- Menyediakan entrypoint `osm mcp` yang mengimplementasikan protokol standard Anthropic Model Context Protocol via stdio dan SSE.
- Mengekspos tools sistem:
  - `osm_safe_exec`: Runner tereksekusi dengan validasi AST dan fallback sandbox.
  - `osm_telemetry`: Streaming metrik sistem (CPU, RAM, zRAM, thermal, storage latency).
  - `osm_sandbox`: Kontrol virtualisasi workspace.
  - `osm_tune`: Endpoint hardware/kernel tuning.

### Pilar 3: Deterministic Zero-Trust Security Upgrade
- **Shell AST Semantic Analysis**: Menggantikan POSIX regex dengan Python AST analysis (`bashlex` / tree-sitter-bash) di `os_manager/security/ast_guard.py` untuk mengidentifikasi redirection (`>`, `>>`, `| tee`), parameter expansion, dan subshell evaluation.
- **Bubblewrap (`bwrap`) Ephemeral Sandbox**: Fallback eksekusi rootless yang ringan dan cepat tanpa overhead Docker/Podman (`--ro-bind / /`, `--tmpfs /tmp`, `--unshare-net`).

### Pilar 4: Multi-Agent Orchestration Protocol & State Ledger
- **Structured State Ledger**: Mengganti ephemeral Unix socket messaging di `scripts/agent_bus.py` dengan persistent event store berbasis SQLite WAL (`~/.local/state/osm/ledger.db`).
- **Distributed Concurrency & Locks**: Advisory locking berbasis file/SQLite untuk mencegah tabrakan workspace antar subagent di Tmux session (`scripts/tmux_agents.sh`).
- **Standard Handoff Specification**: Struktur handover context formal (memory snapshot, worktree branch pointer, task capability lease).

### Pilar 5: Developer Experience, Packaging & Community
- **Declarative Configuration (`.osm.toml`)**: Universal configuration manifest yang menggantikan hardcoded constants.
- **Distribution Matrix**: PyPI packaging (`0xrizz-os-manager`), Homebrew Formula (`brew install 0xrizz/tap/osm`), Arch AUR (`PKGBUILD`), dan standalone binary release via GitHub Actions.
- **Unified Pytest Matrix**: Konsolidasi 37 shell tests ke parameterized `pytest` test suites dengan mock sysfs/DMI fixtures.

---

## 4. Matriks Prioritas Implementasi (Impact vs Effort)

```text
              IMPACT
                ^
                |   [QW-1] Declarative Config      [CM-1] AST Guard & bwrap (RFC-001)
           High |   [QW-2] Redirection Hotfix      [CM-2] Dynamic HAL Engine (RFC-002)
                |                                  [CM-3] Native MCP Server
                |
                |   [QW-3] Unified Pytest          [CM-4] Multi-Agent Ledger & Locks
            Low |                                  [EE-1] Package Distribution (Brew/AUR)
                |                                  [EE-2] Visual TUI Monitor
                +────────────────────────────────────────────────────────────────────────>
                    Low Complexity                 High Complexity                EFFORT
```

| ID | Inisiatif | Kategori | Kompleksitas | Dampak | Target Rilis | Deliverables Utama |
|---|---|---|---|---|---|---|
| **QW-1** | Declarative Config Loader (`.osm.toml`) | Quick Win | Low | High | v1.1.0 | Standard library TOML parser, deprecate hardcoded paths di `tune.py`. |
| **QW-2** | Regex Guard Redirection Hotfix | Quick Win | Low | High | v1.1.0 | Tambahkan redirection check (`>`, `>>`) dan eval check di `pre_tool_guard.sh`. |
| **QW-3** | Unified Pytest Migration | Quick Win | Med | Med | v1.1.0 | Konversi 37 shell tests ke `pytest-subtests` dengan fixture mock sysfs. |
| **CM-1** | AST Parser & bwrap Sandbox (RFC-001) | Core Milestone | High | Critical | v1.2.0 | Engine `osm-guard` berbasis `bashlex` + jail execution via `bwrap`. |
| **CM-2** | Dynamic HAL & Universal Profiler (RFC-002) | Core Milestone | High | High | v1.2.0 | `os_manager/platform/hal/` dengan auto-discovery sysfs/DMI & multi-vendor driver. |
| **CM-3** | Native MCP Server Integration | Core Milestone | Med | High | v1.3.0 | Module `os_manager/mcp/` implementasi standard Anthropic MCP JSON-RPC. |
| **CM-4** | Multi-Agent State Ledger & Locking | Core Milestone | Med | Med | v1.3.0 | SQLite WAL backend, distributed mutex lock di `agent_bus.py`. |
| **EE-1** | Multi-Distro Packaging (Brew, AUR, Deb) | Ecosystem | Med | Med | v1.4.0 | Homebrew tap, Debian `.deb`, AUR PKGBUILD, CI/CD pipeline. |
| **EE-2** | Visual TUI Dashboard & Monitor | Ecosystem | High | Med | v2.0.0 | Terminal UI monitor berbasis `textual` / `curses`. |

---

## 5. Technical Specifications / Mini-RFCs untuk 2 Inisiatif Prioritas Tertinggi

---

### Mini-RFC 001: AST-Based Tool Guard with Bubblewrap Sandboxing

#### 1. Problem Statement
`scripts/hooks/pre_tool_guard.sh` menggunakan regex string sederhana. Pola ini rentan terhadap obfuscation (`eval`, `base64`), subshell variable expansion, dan file redirection (`cat bad > /etc/passwd`) yang dipanggil via tool `Bash`. Mekanisme fallback Podman saat ini bersifat fail-open jika container runtime tidak terpasang.

#### 2. Technical Architecture
```text
 ┌────────────────────────────────────────────────────────┐
 │       Tool Call JSON Payload (Bash / Edit / Write)     │
 └───────────────────────────┬────────────────────────────┘
                             │
 ┌───────────────────────────▼────────────────────────────┐
 │  osm-guard PreTool Engine (os_manager/security/guard)  │
 └───────────────────────────┬────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
 ┌──────────────────────┐          ┌──────────────────────┐
 │ File I/O Canonical   │          │ Shell AST Parser     │
 │ Path Validator       │          │ (bashlex AST Walk)   │
 └──────────┬───────────┘          └──────────┬───────────┘
            │                                 │
            │   ┌─────────────────────────────┴─────────────────────────────┐
            │   │ • Redirection Target Extraction (>, >>, | tee)            │
            │   │ • Eval & Base64 Dynamic Unpack Inspection                 │
            │   │ • Destructive Binary Name Check (mkfs, fdisk, dd, rm)     │
            │   └─────────────────────────────┬─────────────────────────────┘
            │                                 │
 ┌──────────▼─────────────────────────────────▼───────────┐
 │ Policy Rule Evaluation (.osm.toml [security])          │
 └───────────────────────────┬────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
 ┌──────────────────────┐          ┌──────────────────────┐
 │ Invariant Violation  │          │ Safe or Sandboxed    │
 │ (Exit Code 2 Block)  │          │ (Exit Code 0 / bwrap)│
 └──────────────────────┘          └──────────────────────┘
```

#### 3. Configuration Schema (`.osm.toml`)
```toml
[security]
profile = "strict"              # strict | standard | permissive
engine = "ast"                  # ast | legacy_regex
fail_action = "deny"            # deny | prompt | isolate

[security.sandbox]
backend = "bubblewrap"          # bubblewrap | podman | none
auto_isolate_dangerous = true
network_isolation = true
read_only_root = true
writable_paths = [
    ".",
    "/tmp",
    "~/.cache"
]

[security.invariants]
deny_paths = [
    "/etc/shadow",
    "/etc/passwd",
    "/etc/sudoers",
    "/boot/**",
    "/dev/**",
    "/mnt/c/Windows/**"
]
deny_commands = [
    "mkfs", "fdisk", "parted", "dd",
    "wsl --unregister", "wsl --terminate"
]
```

#### 4. Interface Contract & Pseudocode
```python
# os_manager/security/ast_guard.py
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Any
import bashlex

@dataclass(frozen=True)
class PolicyViolation:
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM"
    node_type: str
    target: str
    reason: str

class ShellASTValidator:
    def __init__(self, protected_paths: List[str], blocked_binaries: List[str]):
        self.protected_paths = [str(Path(p).resolve()) for p in protected_paths]
        self.blocked_binaries = set(blocked_binaries)

    def analyze_command(self, raw_cmd: str) -> Tuple[bool, List[PolicyViolation]]:
        violations: List[PolicyViolation] = []
        try:
            parts = bashlex.parse(raw_cmd)
        except Exception:
            return False, [PolicyViolation("CRITICAL", "Syntax", raw_cmd, "Unparseable shell syntax - fail closed")]

        for node in parts:
            self._walk_node(node, raw_cmd, violations)

        return len(violations) == 0, violations

    def _walk_node(self, node: Any, raw_cmd: str, violations: List[PolicyViolation]) -> None:
        # 1. Intercept file output redirections: e.g. cat payload > /etc/passwd
        if hasattr(node, "redirects"):
            for redir in node.redirects:
                if hasattr(redir, "output") and hasattr(redir.output, "word"):
                    target = str(Path(redir.output.word).resolve())
                    if any(target.startswith(p) for p in self.protected_paths):
                        violations.append(PolicyViolation(
                            "CRITICAL", "Redirection", target,
                            f"Attempted write redirection to protected path: {target}"
                        ))

        # 2. Command node evaluation
        if node.kind == "command":
            words = [raw_cmd[p.pos[0]:p.pos[1]] for p in node.parts if p.kind == "word"]
            if words:
                executable = Path(words[0]).name
                if executable in self.blocked_binaries:
                    violations.append(PolicyViolation(
                        "CRITICAL", "Command", executable,
                        f"Execution of destructive command forbidden: {executable}"
                    ))
                if executable in ("eval", "exec"):
                    violations.append(PolicyViolation(
                        "HIGH", "DynamicExecution", executable,
                        "Dynamic evaluation construct forbidden under strict security policy"
                    ))

        # Recursive walk
        if hasattr(node, "parts"):
            for child in node.parts:
                self._walk_node(child, raw_cmd, violations)
```

```bash
# Ephemeral Sandbox Wrapper: scripts/sandbox_bwrap.sh
#!/usr/bin/env bash
set -euo pipefail

TARGET_CMD="$*"
WORKSPACE_DIR="$(pwd)"

bwrap \
    --ro-bind / / \
    --dev /dev \
    --proc /proc \
    --tmpfs /tmp \
    --tmpfs /run \
    --bind "${WORKSPACE_DIR}" "${WORKSPACE_DIR}" \
    --bind "${HOME}/.cache" "${HOME}/.cache" \
    --unshare-all \
    --share-net \
    --die-with-parent \
    --chdir "${WORKSPACE_DIR}" \
    /bin/bash -c "${TARGET_CMD}"
```

---

### Mini-RFC 002: Dynamic Hardware Abstraction Layer (HAL) & Universal Profiler

#### 1. Problem Statement
Subcommand `osm tune` dan modul `scripts/tune_hardware.sh` mengasumsikan sistem target adalah Lenovo IdeaPad 3 15IIL05 dengan Intel Ice Lake dan Realtek ALC298. Hal ini menyebabkan kegagalan eksekusi pada vendor hardware lain, merusak portabilitas open-source, dan berisiko salah konfigurasi pada hardware non-target.

#### 2. Architecture & Driver Plugin Registry
```text
 ┌────────────────────────────────────────────────────────┐
 │           CLI / Daemon Invocations (osm tune)          │
 └───────────────────────────┬────────────────────────────┘
                             │
 ┌───────────────────────────▼────────────────────────────┐
 │  HAL Engine & HardwareRegistry (os_manager/platform)   │
 └───────────────────────────┬────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
 ┌──────────────────────┐          ┌──────────────────────┐
 │ DMI / Sysfs Detector │          │ Storage & Block Walk │
 │ • Vendor / Model     │          │ • /sys/block/*/queue │
 │ • CPU Microarch      │          │ • findmnt / -no SRC  │
 └──────────┬───────────┘          └──────────┬───────────┘
            │                                 │
 ┌──────────▼─────────────────────────────────▼───────────┐
 │ Concrete HardwareDriver Selector                       │
 └───────────────────────────┬────────────────────────────┘
                             │
       ┌──────────────┬──────┴──────┬──────────────┬──────────────┐
       ▼              ▼             ▼              ▼              ▼
┌──────────────┐┌────────────┐┌────────────┐┌─────────────┐┌────────────┐
│ LenovoDriver ││ ThinkPad   ││ AsusDriver ││GenericLinux ││DarwinDriver│
│ • VPC2004    ││ • thinkpad_││ • asus_wmi ││ • ACPI plat_││ • pmset    │
│ • Conserv.   ││   acpi     ││ • Fan Prof.││   profile   ││ • sysctl   │
└──────────────┘└────────────┘└────────────┘└─────────────┘└────────────┘
```

#### 3. Configuration Schema (`.osm.toml`)
```toml
[hardware]
driver = "auto"                 # auto | lenovo | thinkpad | asus | dell | generic | macos
force_override = false

[hardware.storage]
target_disks = ["auto"]         # auto = discover root disk via mount points; or explicit ["/dev/nvme0n1", "/dev/sda"]
scheduler_ssd = "bfq"
scheduler_nvme = "none"
nr_requests = 1024

[hardware.power]
ac_profile = "performance"      # performance | balanced | low-power
battery_profile = "low-power"
battery_conservation_limit = 80 # Battery Charge Threshold (vendor supported)

[hardware.overrides.sysfs]
# Custom sysfs mapping jika vendor belum didukung native
platform_profile = "/sys/firmware/acpi/platform_profile"
charge_threshold = "/sys/class/power_supply/BAT0/charge_control_end_threshold"
```

#### 4. Interface Contract & Python Driver Implementation
```python
# os_manager/platform/hal/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class AbstractHardwareDriver(ABC):
    @abstractmethod
    def probe(self) -> bool:
        """Return True if this driver supports the running hardware platform."""
        pass

    @abstractmethod
    def get_platform_profile(self) -> Dict[str, Any]:
        """Return current and available ACPI platform profiles."""
        pass

    @abstractmethod
    def set_platform_profile(self, profile: str) -> bool:
        """Set ACPI thermal performance profile."""
        pass

    @abstractmethod
    def get_battery_conservation(self) -> Dict[str, Any]:
        """Query battery charge threshold."""
        pass

    @abstractmethod
    def set_battery_conservation(self, enabled: bool) -> bool:
        """Apply battery charge limiting threshold."""
        pass
```

```python
# os_manager/platform/hal/generic_linux.py
from pathlib import Path
from typing import Dict, Any, List
from .base import AbstractHardwareDriver

class GenericLinuxDriver(AbstractHardwareDriver):
    ACPI_PROFILE = Path("/sys/firmware/acpi/platform_profile")
    ACPI_CHOICES = Path("/sys/firmware/acpi/platform_profile_choices")

    def probe(self) -> bool:
        return self.ACPI_PROFILE.exists()

    def get_platform_profile(self) -> Dict[str, Any]:
        if not self.ACPI_PROFILE.exists():
            return {"supported": False, "current": "unsupported", "choices": []}
        current = self.ACPI_PROFILE.read_text(encoding="utf-8").strip()
        choices: List[str] = []
        if self.ACPI_CHOICES.exists():
            choices = self.ACPI_CHOICES.read_text(encoding="utf-8").strip().split()
        return {"supported": True, "current": current, "choices": choices}

    def set_platform_profile(self, profile: str) -> bool:
        info = self.get_platform_profile()
        if not info["supported"]:
            return False
        if info["choices"] and profile not in info["choices"]:
            raise ValueError(f"Profile '{profile}' not supported: {info['choices']}")
        self.ACPI_PROFILE.write_text(profile, encoding="utf-8")
        return True

    def get_battery_conservation(self) -> Dict[str, Any]:
        for bat in Path("/sys/class/power_supply").glob("BAT*"):
            thresh = bat / "charge_control_end_threshold"
            if thresh.exists():
                return {"supported": True, "threshold": int(thresh.read_text().strip())}
        return {"supported": False, "threshold": None}

    def set_battery_conservation(self, enabled: bool) -> bool:
        target = 80 if enabled else 100
        applied = False
        for bat in Path("/sys/class/power_supply").glob("BAT*"):
            thresh = bat / "charge_control_end_threshold"
            if thresh.exists():
                thresh.write_text(str(target), encoding="utf-8")
                applied = True
        return applied
```

```python
# os_manager/platform/hal/registry.py
from typing import List
from .base import AbstractHardwareDriver
from .lenovo import LenovoDriver
from .generic_linux import GenericLinuxDriver
from .macos import DarwinDriver

class HardwareRegistry:
    def __init__(self):
        self._drivers: List[AbstractHardwareDriver] = [
            LenovoDriver(),
            DarwinDriver(),
            GenericLinuxDriver(),  # Fallback standard ACPI
        ]

    def get_active_driver(self) -> AbstractHardwareDriver:
        for driver in self._drivers:
            if driver.probe():
                return driver
        raise RuntimeError("No compatible hardware driver found for this platform.")
```

---

## 6. Verification & Migration Strategy

1. **Unit & Integration Testing**:
   - `python3 -m unittest discover -s tests -p "test_*.py"` (all 19 existing test modules passing).
   - AST validator security test suite against obfuscated payloads (`base64`, `eval`, `tee`, file redirections).
2. **Platform & Hardware Emulation**:
   - Mock sysfs/DMI paths in `tests/test_hal.py` to assert correct driver fallback across Lenovo, Asus, Dell, and generic Linux.
3. **Deterministic Harness Latency**:
   - Execute `./scripts/hook_benchmark.sh` and `./tests/test_harness.sh` to guarantee p99 hook execution stays under 15ms.
