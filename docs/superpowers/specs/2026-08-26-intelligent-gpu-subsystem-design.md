# Design Specification: Intelligent Dual-GPU Subsystem & Workload Routing

- **Document ID**: `SPEC-2026-08-26-GPU-SUBSYSTEM`
- **Target Platform**: Debian 13 (Trixie) Linux Native / Lenovo IdeaPad (Hardware Product `81WD`)
- **Kernel & Architecture**: Linux `6.12.101+deb13-amd64`, x86_64
- **Dual-GPU Topology**:
  - Primary iGPU: Intel Iris Plus Graphics G1 (`[8086:8a56]`, Ice Lake-LP, Driver `i915`, VA-API `iHD`)
  - Discrete dGPU: NVIDIA GeForce MX330 (`[10de:1d16]`, Pascal GP108M, 384 CUDA Cores)

---

## 1. Problem Statement & Motivation

On hybrid Linux laptops, desktop applications (such as Spotube, web browsers, and media players) frequently suffer from inefficient CPU rendering loops or inappropriate GPU allocation. Conversely, heavy 3D and AI workloads fail to leverage discrete NVIDIA acceleration due to missing proprietary drivers or missing Freedesktop PRIME launch configurations.

The `os-manager` control plane requires an autonomous, intelligent GPU subsystem that:
1. Audits dual-GPU state, driver flavors, power-gating states (PCIe Runtime D3Cold), and acceleration capabilities.
2. Automates non-interactive driver provisioning with strict architecture enforcement (blocking `nvidia-open-kernel-dkms` on Pascal architectures).
3. Automatically classifies and routes desktop application workloads so that lightweight/media apps default to Intel VA-API, while heavy 3D/engineering/AI applications automatically launch via NVIDIA PRIME offloading without user friction.
4. Manages runtime power profiles persistently across system reboots.

---

## 2. Architecture & Component Decomposition

```text
os-manager/
├── os_manager/
│   ├── cli.py                   # Main CLI argument parser entrypoint routing 'gpu' and 'diag'
│   ├── commands/
│   │   ├── gpu.py               # GPU Command Controller (status, install, run, sync-profiles, profile)
│   │   └── diag.py              # Extended diagnostic engine exposing GPU subsystem telemetry
│   └── platform/
│       └── hal/
│           ├── base.py          # Data models: GpuDeviceInfo, GpuSubsystemInfo
│           ├── generic_linux.py # Sysfs & PCIe scanner for multi-vendor GPUs
│           └── gpu_classifier.py# Heuristic workload classifier & desktop profile synchronizer
├── tests/
│   ├── gpu/
│   │   ├── test_gpu_classifier.py # Test suite for .desktop category heuristics
│   │   └── test_gpu_hal.py        # Test suite for sysfs/lspci mocking
│   └── test_cli.py                # CLI routing assertions
└── docs/superpowers/specs/
    └── 2026-08-26-intelligent-gpu-subsystem-design.md
```

---

## 3. Data Models & HAL Abstraction

### 3.1 `GpuDeviceInfo` & `GpuSubsystemInfo` (`os_manager/platform/hal/base.py`)

```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class GpuDeviceInfo:
    vendor: str                 # "Intel", "NVIDIA"
    device_name: str            # "Iris Plus Graphics G1", "GeForce MX330"
    pci_slot: str               # "0000:00:02.0", "0000:01:00.0"
    driver_in_use: str          # "i915", "nvidia", "nouveau", "none"
    is_discrete: bool           # False (iGPU), True (dGPU)
    power_state: str            # "active", "suspended", "unsupported"
    vaapi_supported: bool       # True for Intel Gen8+ media driver
    cuda_supported: bool        # True for NVIDIA CUDA devices

@dataclass
class GpuSubsystemInfo:
    primary_display_gpu: Optional[GpuDeviceInfo]
    discrete_gpu: Optional[GpuDeviceInfo]
    active_profile: str         # "hybrid", "performance", "powersave"
    driver_flavor: str          # "proprietary", "nouveau", "missing"
```

---

## 4. Intelligent Workload Classifier & Profile Synchronizer (`gpu_classifier.py`)

### 4.1 Categorization Rules
The classifier categorizes applications discovered in `/usr/share/applications` and `/var/lib/flatpak/exports/share/applications/`:

| Target GPU | Freedesktop Categories / Binary Keywords | Optimization Strategy |
| :--- | :--- | :--- |
| **Intel Iris Plus (iGPU)** | `AudioVideo;Player;`, `Audio;`, `WebBrowser;`, `Office;`, `Utility;`, `TextEditor;` | Assigned to primary display; accelerated by Intel VA-API (`LIBVA_DRIVER_NAME=iHD`). |
| **NVIDIA MX330 (dGPU)** | `Game;`, `3DGraphics;`, `Graphics;3D;`, `Science;Engineering;`, `VideoEditing;`, `Blender`, `Godot`, `Steam`, `DaVinci`, `Ollama`, `PyTorch` | Configured with `PrefersNonDefaultGPU=true` and `X-KDE-RunOnDiscreteGpu=true`. |

### 4.2 Synchronization Protocol (`sync-profiles`)
1. Scan system desktop entries.
2. When an application matches dGPU heuristic rules and does not have an existing override in `~/.local/share/applications/`, generate an override `.desktop` file.
3. Inject the keys:
   ```ini
   PrefersNonDefaultGPU=true
   X-KDE-RunOnDiscreteGpu=true
   ```
4. Trigger desktop database update (`update-desktop-database ~/.local/share/applications/` if available).

---

## 5. Command Controller Specifications (`osm gpu`)

### 5.1 `osm gpu status [--json]`
- Inspects `/sys/bus/pci/devices/0000:01:00.0/power/runtime_status`.
- Inspects `/sys/bus/pci/devices/0000:00:02.0/` for Intel display engine.
- Queries `nvidia-smi` (if installed) for VRAM, temperature, and driver version.
- Emits formatted TTY report or JSON payload.

### 5.2 `osm gpu install [--cuda] [--dry-run]`
- Checks running kernel version and header availability (`linux-headers-$(uname -r)`).
- Enforces proprietary flavor: Installs `nvidia-kernel-dkms`, `nvidia-driver`, `firmware-misc-nonfree`, `intel-media-va-driver-non-free`.
- Strictly forbids and rejects `nvidia-open-kernel-dkms` when Pascal GPU (`[10de:1d16]`) is detected.
- If `--cuda` is specified, adds official NVIDIA CUDA network repository key and installs CUDA toolkit.
- Configures `/etc/modprobe.d/nvidia-pm.conf` with `options nvidia "NVreg_DynamicPowerManagement=0x02"`.

### 5.3 `osm gpu run <command...>`
Executes user command wrapped with PRIME render offload environment variables:
```bash
__NV_PRIME_RENDER_OFFLOAD=1 \
__GLX_VENDOR_LIBRARY_NAME=nvidia \
__VK_LAYER_NV_optimus=non_NVIDIA_only \
exec "$@"
```

### 5.4 `osm gpu profile [hybrid|performance|powersave]`
- `hybrid`: `NVreg_DynamicPowerManagement=0x02` (Auto D3Cold sleep when idle).
- `performance`: `NVreg_DynamicPowerManagement=0x00` (NVIDIA dGPU always on).
- `powersave`: Forces PCIe runtime control `auto` and unbinds non-essential kernel interfaces.

---

## 6. Error Recovery & Guardrail Invariants

1. **Non-Interactive Sudo Streaming**: Privileged operations resolve credentials from `${CLAUDE_PROJECT_DIR}/.env` (`SUDO_PASSWORD=...`) and stream via `sudo -S` without blocking on interactive TTY prompts.
2. **PreToolUse Tier Compliance**: Modprobe and udev configuration operations strictly follow Tier 2 execution patterns.
3. **DKMS Build Guard**: If DKMS module build fails, system gracefully falls back to Intel i915 rendering without breaking the active desktop session.

---

## 7. Testing & Verification Plan

1. **Unit Tests**:
   - `tests/gpu/test_gpu_classifier.py`: Validate heuristic matching against mock `.desktop` files.
   - `tests/gpu/test_gpu_hal.py`: Validate sysfs parsing, runtime status detection, and lspci output decoding.
   - `tests/test_cli.py`: Assert `osm gpu` subcommand routing and exit codes.
2. **Regression & Quality Suite**:
   - Run master harness test suite: `./tests/test_harness.sh`.
   - Run complete pytest suite: `.venv/bin/pytest tests/`.
