# Specification: Cross-Distribution Engine Architecture

- **Date:** 2026-08-19
- **Scope:** Cross-Distribution WSL2 Governance (`/home/rizz/dev/os-manager`)
- **Status:** Approved
- **Deliverable Reference:** Phase 4, Deliverable 4.1

---

## 1. Executive Summary

`os-manager` began as a control plane specialized for Debian 13 (Trixie) WSL2 instances. As developer environments diversify across enterprise and open-source ecosystems, developer workstations frequently run Ubuntu (LTS and intermediate releases), Arch Linux (rolling release), and Fedora Linux (Workstation and Silverblue). 

The Cross-Distribution Engine extends `os-manager` governance to Debian, Ubuntu, Arch Linux, and Fedora WSL2 environments. It introduces a modular POSIX shell library (`scripts/lib/distro.sh`) and normalizes package management. Harness rules in `scripts/hooks/pre_tool_guard.sh` expand Tier 3 security checks to block destructive package purges across APT, Pacman, DNF, Zypper, and APK. Unified diagnostic telemetry ensures consistent observability across all supported Linux distributions.

---

## 2. Problem Statement and Architectural Goals

### Current Limitations
1. **Hardcoded Package Manager Invocations**: Existing automation scripts (`scripts/clean_system.sh`, `scripts/update_runtimes.sh`) invoke `sudo apt` directly, failing on Arch Linux (`pacman`) and Fedora (`dnf`).
2. **Narrow Security Guardrails**: `scripts/hooks/pre_tool_guard.sh` enforces Tier 3 package manager invariants solely against `apt purge *` and `apt remove -y *`, leaving other package managers unguarded against destructive wildcard commands.
3. **Distribution-Specific Diagnostics**: `scripts/sys_diag.sh` assumes Debian-specific system paths and APT package tracking.

### Architectural Goals
- **Distribution Agnosticism**: Provide a single shared library (`scripts/lib/distro.sh`) that transparently discovers the host environment and exports standard operational primitives.
- **Normalized Package Operations**: Expose clean functional abstractions (`pkg_update`, `pkg_upgrade`, `pkg_clean`, `pkg_install`) with non-interactive flags enabled.
- **Generalized Security Invariants**: Expand the PreToolUse regex engine to block catastrophic package purge commands across APT, Pacman, DNF, Zypper, and APK.
- **Zero-Overhead Sourcing**: Maintain sub-millisecond library load times to protect hook performance metrics (<10ms target).

---

## 3. Distribution Discovery Engine (`scripts/lib/distro.sh`)

### Discovery Topology

```text
 ┌─────────────────────────────────────────────────────────────┐
 │                 Host System Initialization                  │
 └──────────────────────────────┬──────────────────────────────┘
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                Inspect /etc/os-release                      │
 │     (Fallback: hostnamectl -> which pacman/dnf/apt)         │
 └──────────────────────────────┬──────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
 ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
 │ Family:      │        │ Family:      │        │ Family:      │
 │ debian       │        │ arch         │        │ fedora       │
 ├──────────────┤        ├──────────────┤        ├──────────────┤
 │• Debian 12/13│        │• Arch Linux  │        │• Fedora 39-41│
 │• Ubuntu 22/24│        │• EndeavourOS │        │• CentOS / RHEL│
 │• Pop!_OS     │        │• Manjaro     │        │• Rocky Linux │
 └──────┬───────┘        └──────┬───────┘        └──────┬───────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                │
                                ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                Exported Standard Primitives                 │
 │ • pkg_update()    • pkg_upgrade()                           │
 │ • pkg_clean()     • pkg_install()                           │
 └─────────────────────────────────────────────────────────────┘
```

### Discovery Algorithm and Metadata Exports

The library parses standard `/etc/os-release` fields (`ID`, `ID_LIKE`, `VERSION_ID`) and exports the following normalized variables into the executing shell environment:

```bash
# Sourced via: . "${WORKSPACE_ROOT}/scripts/lib/distro.sh"

export OS_DISTRO_ID        # e.g., "debian", "ubuntu", "arch", "fedora"
export OS_DISTRO_FAMILY    # e.g., "debian", "arch", "fedora", "generic"
export OS_DISTRO_VERSION   # e.g., "13", "24.04", "rolling", "40"
export OS_DISTRO_NAME      # e.g., "Debian GNU/Linux 13 (trixie)"
export OS_PKG_MANAGER      # e.g., "apt", "pacman", "dnf"
export OS_SERVICE_MANAGER  # e.g., "systemd"
```

### Parsing Implementation Specification

```bash
#!/usr/bin/env bash
# scripts/lib/distro.sh - Cross-Distribution Detection & Package Abstraction
set -euo pipefail

detect_distro() {
    if [ -f /etc/os-release ]; then
        # shellcheck disable=SC1091
        . /etc/os-release
        OS_DISTRO_ID="${ID:-unknown}"
        OS_DISTRO_NAME="${PRETTY_NAME:-Linux}"
        OS_DISTRO_VERSION="${VERSION_ID:-rolling}"
        
        case "${OS_DISTRO_ID}" in
            debian|ubuntu|pop|linuxmint|kali)
                OS_DISTRO_FAMILY="debian"
                OS_PKG_MANAGER="apt"
                ;;
            arch|endeavouros|manjaro|artix)
                OS_DISTRO_FAMILY="arch"
                OS_PKG_MANAGER="pacman"
                ;;
            fedora|rhel|centos|rocky|alma)
                OS_DISTRO_FAMILY="fedora"
                OS_PKG_MANAGER="dnf"
                ;;
            *)
                # Check ID_LIKE fallback
                if [[ "${ID_LIKE:-}" =~ (debian|ubuntu) ]]; then
                    OS_DISTRO_FAMILY="debian"
                    OS_PKG_MANAGER="apt"
                elif [[ "${ID_LIKE:-}" =~ (arch) ]]; then
                    OS_DISTRO_FAMILY="arch"
                    OS_PKG_MANAGER="pacman"
                elif [[ "${ID_LIKE:-}" =~ (fedora|rhel) ]]; then
                    OS_DISTRO_FAMILY="fedora"
                    OS_PKG_MANAGER="dnf"
                else
                    OS_DISTRO_FAMILY="generic"
                    OS_PKG_MANAGER="unknown"
                fi
                ;;
        esac
    else
        # Fallback heuristic based on binary discovery
        if command -v apt-get &>/dev/null; then
            OS_DISTRO_ID="debian"
            OS_DISTRO_FAMILY="debian"
            OS_PKG_MANAGER="apt"
        elif command -v pacman &>/dev/null; then
            OS_DISTRO_ID="arch"
            OS_DISTRO_FAMILY="arch"
            OS_PKG_MANAGER="pacman"
        elif command -v dnf &>/dev/null; then
            OS_DISTRO_ID="fedora"
            OS_DISTRO_FAMILY="fedora"
            OS_PKG_MANAGER="dnf"
        else
            OS_DISTRO_ID="generic"
            OS_DISTRO_FAMILY="generic"
            OS_PKG_MANAGER="unknown"
        fi
        OS_DISTRO_NAME="Generic Linux"
        OS_DISTRO_VERSION="unknown"
    fi

    OS_SERVICE_MANAGER="systemd"
    export OS_DISTRO_ID OS_DISTRO_FAMILY OS_DISTRO_VERSION OS_DISTRO_NAME OS_PKG_MANAGER OS_SERVICE_MANAGER
}

# Run detection on source
detect_distro
```

---

## 4. Normalized Package Management Interface

`scripts/lib/distro.sh` implements unified lifecycle wrappers for package updates, system upgrades, cache eviction, and package installation.

### Functional Matrix

| Function | Debian / Ubuntu (`apt`) | Arch Linux (`pacman`) | Fedora (`dnf`) |
| :--- | :--- | :--- | :--- |
| **`pkg_update`** | `sudo apt update` | `sudo pacman -Sy` | `sudo dnf check-update \|\| [ $? -eq 100 ]` |
| **`pkg_upgrade`** | `sudo apt upgrade -y` | `sudo pacman -Syu --noconfirm` | `sudo dnf upgrade -y` |
| **`pkg_clean`** | `sudo apt autoremove -y && sudo apt clean` | `sudo pacman -Sc --noconfirm` (+ `paccache -r` if present) | `sudo dnf autoremove -y && sudo dnf clean all` |
| **`pkg_install <pkgs>`** | `sudo apt install -y <pkgs>` | `sudo pacman -S --noconfirm --needed <pkgs>` | `sudo dnf install -y <pkgs>` |

### Detailed Function Definitions

```bash
pkg_update() {
    case "${OS_DISTRO_FAMILY}" in
        debian)
            sudo apt update "$@"
            ;;
        arch)
            sudo pacman -Sy "$@"
            ;;
        fedora)
            sudo dnf check-update "$@" || [ $? -eq 100 ]
            ;;
        *)
            echo "[distro.sh] Unsupported package family: ${OS_DISTRO_FAMILY}" >&2
            return 1
            ;;
    esac
}

pkg_upgrade() {
    case "${OS_DISTRO_FAMILY}" in
        debian)
            sudo apt upgrade -y "$@"
            ;;
        arch)
            sudo pacman -Syu --noconfirm "$@"
            ;;
        fedora)
            sudo dnf upgrade -y "$@"
            ;;
        *)
            echo "[distro.sh] Unsupported package family: ${OS_DISTRO_FAMILY}" >&2
            return 1
            ;;
    esac
}

pkg_clean() {
    case "${OS_DISTRO_FAMILY}" in
        debian)
            sudo apt autoremove -y
            sudo apt clean
            ;;
        arch)
            sudo pacman -Sc --noconfirm
            if command -v paccache &>/dev/null; then
                sudo paccache -r || true
            fi
            ;;
        fedora)
            sudo dnf autoremove -y
            sudo dnf clean all
            ;;
        *)
            echo "[distro.sh] Unsupported package family: ${OS_DISTRO_FAMILY}" >&2
            return 1
            ;;
    esac
}

pkg_install() {
    if [ $# -eq 0 ]; then
        echo "Usage: pkg_install <package_name...>" >&2
        return 1
    fi

    case "${OS_DISTRO_FAMILY}" in
        debian)
            sudo apt install -y "$@"
            ;;
        arch)
            sudo pacman -S --noconfirm --needed "$@"
            ;;
        fedora)
            sudo dnf install -y "$@"
            ;;
        *)
            echo "[distro.sh] Unsupported package family: ${OS_DISTRO_FAMILY}" >&2
            return 1
            ;;
    esac
}
```

---

## 5. Security Guardrail Invariant Generalization

### Generalized Tier 3 Invariant Filters (`scripts/hooks/pre_tool_guard.sh`)

`pre_tool_guard.sh` enforces deterministic blocks against destructive package manager purges. We expand the regular expression filters to intercept catastrophic package removals across all major Linux package managers:

```bash
# Invariant Block: Package Manager Catastrophic Wildcard Removal across All Distros
if echo "${CMD}" | grep -qE '\b(apt|apt-get|pacman|dnf|zypper|apk)\s+(purge|remove|-Rcs)\s+(\*|all|--all)\b' || \
   echo "${CMD}" | grep -qE '\b(apt|apt-get|dpkg)\s+(--purge\s+)?(purge|remove)\s+-[a-zA-Z0-9]*\*\b' || \
   echo "${CMD}" | grep -qE '\bpacman\s+-[Rksu]+\s+.*(\b|\s)(base|systemd|glibc|linux-firmware)(\b|\s|$)' || \
   echo "${CMD}" | grep -qE '\bdnf\s+(remove|erase)\s+-[a-zA-Z0-9]*\*\b'; then
    echo "[HARNESS SECURITY BLOCKED] Invariant Violation (Tier 3): Destructive mass package removal is strictly forbidden: ${CMD}" >&2
    exit 2
fi
```

### Core Configuration Protection
In addition to `/etc/passwd` and `/etc/shadow`, the file guard rules protect critical package repository files from unverified file edits:
- Debian/Ubuntu: `/etc/apt/sources.list`, `/etc/apt/sources.list.d/**`
- Arch Linux: `/etc/pacman.conf`, `/etc/pacman.d/**`
- Fedora: `/etc/dnf/dnf.conf`, `/etc/yum.repos.d/**`

---

## 6. Automation Scripts Refactoring Plan

| Script Path | Current Behavior | Refactored Architecture |
| :--- | :--- | :--- |
| `scripts/clean_system.sh` | Directly calls `sudo apt autoremove -y && sudo apt clean` | Sources `scripts/lib/distro.sh` and invokes `pkg_clean` |
| `scripts/update_runtimes.sh` | Directly calls `sudo apt update && sudo apt upgrade -y` | Sources `scripts/lib/distro.sh` and invokes `pkg_update` and `pkg_upgrade` |
| `scripts/sys_diag.sh` | Collects Debian-specific information | Queries `OS_DISTRO_NAME`, `OS_DISTRO_FAMILY`, and reports installed package counts via family-specific utilities (`dpkg -l`, `pacman -Q`, `rpm -qa`) |
| `scripts/harness_check.sh` | Verifies Debian package availability | Verifies discovery resolution and validates standard dependencies across the active distribution |
| `scripts/hooks/session_preflight.sh` | Checks for `jq`, `python3`, `node`, `uv` | Logs `OS_DISTRO_ID` and `OS_DISTRO_VERSION` in preflight telemetry payload |

---

## 7. Verification and Automated Test Strategy

### Unit Test Suite Extensions (`tests/test_harness.sh`)

We add 6 automated assertions to `tests/test_harness.sh`:
1. **Assertion 21**: Verify `scripts/lib/distro.sh` loads without error and exports non-empty `OS_DISTRO_FAMILY` and `OS_PKG_MANAGER`.
2. **Assertion 22**: Mock `/etc/os-release` for Arch Linux and verify detection resolves to `family=arch` and `pkg_manager=pacman`.
3. **Assertion 23**: Mock `/etc/os-release` for Fedora and verify detection resolves to `family=fedora` and `pkg_manager=dnf`.
4. **Assertion 24**: Verify `pre_tool_guard.sh` blocks `pacman -Rcs *` with Exit Code 2.
5. **Assertion 25**: Verify `pre_tool_guard.sh` blocks `dnf remove --all` and `apt purge *` with Exit Code 2.
6. **Assertion 26**: Verify `scripts/clean_system.sh` and `scripts/update_runtimes.sh` pass `bash -n` and `shellcheck`.

---

## 8. Rollout Sequence and Implementation DAG

The Cross-Distribution Engine belongs to Stage 1 of the implementation plan:

1. **Stage 1 (Foundation Libraries and Tracing)**:
   - Deliverable 3.4: Hook Performance Tracing (`scripts/hooks/lib/trace_helper.sh`, `scripts/hook_benchmark.sh`).
   - Deliverable 4.1: Cross-Distribution Engine (`scripts/lib/distro.sh`, generalized package guardrails).
2. **Stage 2 (Base System Services, Notifications, and Sandbox)**:
   - Deliverable 3.1: Prometheus Metrics Exporter (`scripts/metrics_exporter.py`).
   - Deliverable 3.3: Desktop Notification Bridge (`scripts/notify_host.sh`).
   - Deliverable 3.2: Automated Host Disk Compaction (`scripts/compact_host_disk.sh`).
   - Deliverable 4.4: Agent Workspace Virtualization (`scripts/sandbox_exec.sh`).
3. **Stage 3 (Multi-Agent Mesh and Disaster Recovery)**:
   - Deliverable 4.2: Inter-Agent Message Bus (`scripts/agent_bus.py`, `scripts/bus_send.sh`).
   - Deliverable 4.3: Automated Disaster Recovery Provisioning (`scripts/bootstrap_wsl.ps1`, `scripts/post_bootstrap.sh`).
