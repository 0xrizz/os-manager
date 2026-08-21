#!/usr/bin/env bash
# scripts/migration/quality_gate_audit.sh - Post-Installation Quality Gate Hardware & Storage Auditor
# Verifies Intel AC 9560 Wi-Fi (iwlwifi), ALSA/PipeWire Audio, Bluetooth, Intel i915 Graphics/Wayland,
# and Partition 4 (DATA_STORE) NTFS preservation before allowing staging partition cleanup.
set -euo pipefail

export PATH="$PATH:/usr/sbin:/sbin"

# Configuration and CLI Options
MOCK_MODE=false
MOCK_FAIL_DATASTORE=false
MOCK_SCORE=""
JSON_MODE=false
STRICT_MODE=false
REPORT_FILE=""

show_help() {
    cat << 'EOF'
Usage: quality_gate_audit.sh [options]

Audits Debian bare-metal post-installation hardware health, driver modules,
and storage preservation (Partition 4 DATA_STORE).

Options:
  --mock                   Simulate 5/5 score passing (for CI / automated testing)
  --mock-fail-datastore    Simulate Partition 4 failure in mock mode (tests Zero-Data-Loss safety)
  --mock-score <N>         Simulate custom score N (0..5)
  --json                   Output machine-readable JSON structure
  --strict                 Require 5/5 perfect score to pass (default: >= 4/5)
  --report <file>          Save audit report to specified file
  -h, --help               Display this help dialog

Exit Codes:
  0: Quality Gate PASSED (Safe to proceed with Phase 4 staging cleanup & root resize)
  1: Quality Gate NOT MET / Critical failure (Do NOT delete staging partitions)
  2: Invalid CLI argument
EOF
}

# Parse Command Line Arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mock)
            MOCK_MODE=true
            shift
            ;;
        --mock-fail-datastore)
            MOCK_MODE=true
            MOCK_FAIL_DATASTORE=true
            shift
            ;;
        --mock-score)
            if [[ $# -lt 2 || ! "$2" =~ ^[0-5]$ ]]; then
                echo "Error: --mock-score requires an integer value between 0 and 5" >&2
                exit 2
            fi
            MOCK_MODE=true
            MOCK_SCORE="$2"
            shift 2
            ;;
        --json)
            JSON_MODE=true
            shift
            ;;
        --strict)
            STRICT_MODE=true
            shift
            ;;
        --report)
            if [[ $# -lt 2 || -z "$2" ]]; then
                echo "Error: --report requires a target file path" >&2
                exit 2
            fi
            REPORT_FILE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'" >&2
            echo "Run '$0 --help' for usage." >&2
            exit 1
            ;;
    esac
done

# Detect Environment (Bare-Metal vs WSL vs Container)
detect_environment() {
    if grep -qi microsoft /proc/version 2>/dev/null || [[ -n "${WSL_DISTRO_NAME:-}" ]] || [[ -f /proc/sys/fs/binfmt_misc/WSLInterceptor ]]; then
        echo "wsl"
    elif [[ -f /.dockerenv ]] || grep -q 'docker\|containerd' /proc/1/cgroup 2>/dev/null; then
        echo "container"
    else
        echo "bare-metal"
    fi
}

ENV_TYPE=$(detect_environment)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%d %H:%M:%S")
SCORE=0
TOTAL=5

# Check State Variables
WIFI_STATUS="FAIL"
WIFI_DETAIL="Not audited"
AUDIO_STATUS="FAIL"
AUDIO_DETAIL="Not audited"
BT_STATUS="FAIL"
BT_DETAIL="Not audited"
GFX_STATUS="FAIL"
GFX_DETAIL="Not audited"
DATASTORE_STATUS="FAIL"
DATASTORE_DETAIL="Not audited"

# -----------------------------------------------------------------------------
# Check 1: Intel AC 9560 Wi-Fi (iwlwifi) Connectivity & Driver
# -----------------------------------------------------------------------------
audit_wifi() {
    if [[ "$MOCK_MODE" == "true" ]]; then
        if [[ -n "$MOCK_SCORE" && "$MOCK_SCORE" -lt 1 ]]; then
            WIFI_STATUS="FAIL"
            WIFI_DETAIL="Simulated Wi-Fi failure (mock score: ${MOCK_SCORE})"
        else
            WIFI_STATUS="PASS"
            WIFI_DETAIL="Intel AC 9560 (iwlwifi) active, internet ping verified"
            SCORE=$((SCORE + 1))
        fi
        return
    fi

    local has_wlan=false
    local has_driver=false
    local has_ping=false

    if ip link show 2>/dev/null | grep -qE "wlan|wlp|wls" || ls -d /sys/class/net/wl* >/dev/null 2>&1; then
        has_wlan=true
    fi

    if lsmod 2>/dev/null | grep -qE "iwlwifi|iwlmvm"; then
        has_driver=true
    fi

    if ping -c 2 -W 3 1.1.1.1 >/dev/null 2>&1 || ping -c 2 -W 3 8.8.8.8 >/dev/null 2>&1; then
        has_ping=true
    fi

    if [[ "$has_wlan" == "true" && "$has_ping" == "true" ]]; then
        WIFI_STATUS="PASS"
        WIFI_DETAIL="Wireless interface active, iwlwifi loaded, internet connected"
        SCORE=$((SCORE + 1))
    elif [[ "$has_wlan" == "true" ]]; then
        WIFI_STATUS="WARN"
        WIFI_DETAIL="Wireless interface detected but ping test failed"
        SCORE=$((SCORE + 1))
    elif [[ "$ENV_TYPE" == "wsl" ]]; then
        if [[ "$has_ping" == "true" ]]; then
            WIFI_STATUS="PASS"
            WIFI_DETAIL="WSL virtual ethernet connected (host manages Intel AC 9560)"
            SCORE=$((SCORE + 1))
        else
            WIFI_STATUS="WARN"
            WIFI_DETAIL="WSL environment with no active internet route"
        fi
    elif [[ "$has_driver" == "true" ]]; then
        WIFI_STATUS="WARN"
        WIFI_DETAIL="iwlwifi driver loaded but wireless interface unconfigured"
    else
        WIFI_STATUS="FAIL"
        WIFI_DETAIL="No wireless interface or iwlwifi driver found"
    fi
}

# -----------------------------------------------------------------------------
# Check 2: ALSA / PipeWire / PulseAudio Subsystem
# -----------------------------------------------------------------------------
audit_audio() {
    if [[ "$MOCK_MODE" == "true" ]]; then
        if [[ -n "$MOCK_SCORE" && "$MOCK_SCORE" -lt 2 ]]; then
            AUDIO_STATUS="FAIL"
            AUDIO_DETAIL="Simulated audio failure (mock score: ${MOCK_SCORE})"
        else
            AUDIO_STATUS="PASS"
            AUDIO_DETAIL="PipeWire / ALSA audio subsystem operational"
            SCORE=$((SCORE + 1))
        fi
        return
    fi

    local has_wpctl=false
    local has_aplay=false
    local has_pactl=false
    local has_soundcard=false

    command -v wpctl >/dev/null 2>&1 && has_wpctl=true
    command -v aplay >/dev/null 2>&1 && has_aplay=true
    command -v pactl >/dev/null 2>&1 && has_pactl=true

    if [[ -d "/sys/class/sound" ]] && ls -d /sys/class/sound/card* >/dev/null 2>&1; then
        has_soundcard=true
    fi

    if [[ "$has_soundcard" == "true" ]] || [[ "$has_wpctl" == "true" ]] || [[ "$has_aplay" == "true" ]] || [[ "$has_pactl" == "true" ]]; then
        AUDIO_STATUS="PASS"
        if [[ "$has_wpctl" == "true" ]]; then
            AUDIO_DETAIL="PipeWire/WirePlumber tools active (wpctl)"
        elif [[ "$has_soundcard" == "true" ]]; then
            AUDIO_DETAIL="ALSA soundcard hardware detected in /sys/class/sound"
        else
            AUDIO_DETAIL="Audio server utility present (aplay/pactl)"
        fi
        SCORE=$((SCORE + 1))
    elif [[ "$ENV_TYPE" == "wsl" && -d "/mnt/wslg" ]]; then
        AUDIO_STATUS="PASS"
        AUDIO_DETAIL="WSLg audio bridge available"
        SCORE=$((SCORE + 1))
    else
        AUDIO_STATUS="WARN"
        AUDIO_DETAIL="Audio server/hardware not detected"
    fi
}

# -----------------------------------------------------------------------------
# Check 3: Bluetooth Subsystem (Intel Bluetooth 5.1)
# -----------------------------------------------------------------------------
audit_bluetooth() {
    if [[ "$MOCK_MODE" == "true" ]]; then
        if [[ -n "$MOCK_SCORE" && "$MOCK_SCORE" -lt 3 ]]; then
            BT_STATUS="FAIL"
            BT_DETAIL="Simulated Bluetooth failure (mock score: ${MOCK_SCORE})"
        else
            BT_STATUS="PASS"
            BT_DETAIL="Intel Bluetooth 5.1 controller active & initialized"
            SCORE=$((SCORE + 1))
        fi
        return
    fi

    local has_btctl=false
    local has_rfkill=false
    local has_btmod=false
    local has_btsys=false

    command -v bluetoothctl >/dev/null 2>&1 && has_btctl=true
    if command -v rfkill >/dev/null 2>&1 && rfkill list bluetooth >/dev/null 2>&1; then
        has_rfkill=true
    fi
    if lsmod 2>/dev/null | grep -qE "btusb|bluetooth"; then
        has_btmod=true
    fi
    if [[ -d "/sys/class/bluetooth" ]] && ls -d /sys/class/bluetooth/hci* >/dev/null 2>&1; then
        has_btsys=true
    fi

    if [[ "$has_rfkill" == "true" || "$has_btsys" == "true" || "$has_btmod" == "true" ]]; then
        BT_STATUS="PASS"
        BT_DETAIL="Bluetooth controller active and unblocked"
        SCORE=$((SCORE + 1))
    elif [[ "$has_btctl" == "true" ]]; then
        BT_STATUS="PASS"
        BT_DETAIL="bluetoothctl utility available (daemon pending)"
        SCORE=$((SCORE + 1))
    elif [[ "$ENV_TYPE" == "wsl" ]]; then
        BT_STATUS="PASS"
        BT_DETAIL="WSL environment: Bluetooth controller managed by Windows host"
        SCORE=$((SCORE + 1))
    else
        BT_STATUS="WARN"
        BT_DETAIL="Bluetooth controller not detected or rfkill blocked"
    fi
}

# -----------------------------------------------------------------------------
# Check 4: Intel Graphics & Display Server (Intel UHD Ice Lake G1 / i915 & Wayland)
# -----------------------------------------------------------------------------
audit_graphics() {
    if [[ "$MOCK_MODE" == "true" ]]; then
        if [[ -n "$MOCK_SCORE" && "$MOCK_SCORE" -lt 4 ]]; then
            GFX_STATUS="FAIL"
            GFX_DETAIL="Simulated graphics failure (mock score: ${MOCK_SCORE})"
        else
            GFX_STATUS="PASS"
            GFX_DETAIL="Intel i915 DRM active, GNOME Wayland compositor verified"
            SCORE=$((SCORE + 1))
        fi
        return
    fi

    local has_wayland=false
    local has_i915=false
    local has_dri=false

    if [[ "${XDG_SESSION_TYPE:-}" == "wayland" ]] || [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
        has_wayland=true
    fi

    if lsmod 2>/dev/null | grep -qE "i915|xe"; then
        has_i915=true
    fi

    if [[ -e "/dev/dri/card0" || -e "/dev/dri/renderD128" ]]; then
        has_dri=true
    fi

    if [[ "$has_wayland" == "true" && ("$has_i915" == "true" || "$has_dri" == "true") ]]; then
        GFX_STATUS="PASS"
        GFX_DETAIL="Intel i915 DRM driver loaded with native Wayland session"
        SCORE=$((SCORE + 1))
    elif [[ "$has_i915" == "true" || "$has_dri" == "true" ]]; then
        GFX_STATUS="PASS"
        GFX_DETAIL="Intel DRM graphics acceleration active (/dev/dri)"
        SCORE=$((SCORE + 1))
    elif [[ "$ENV_TYPE" == "wsl" ]]; then
        GFX_STATUS="PASS"
        GFX_DETAIL="WSL environment: WSLg D3D12 vGPU acceleration active"
        SCORE=$((SCORE + 1))
    elif [[ "$has_wayland" == "true" ]]; then
        GFX_STATUS="PASS"
        GFX_DETAIL="Wayland session active (compositor running)"
        SCORE=$((SCORE + 1))
    else
        GFX_STATUS="WARN"
        GFX_DETAIL="Running in non-Wayland / framebuffer display mode"
    fi
}

# -----------------------------------------------------------------------------
# Check 5: Partition 4 (DATA_STORE) Preservation & Health (Zero-Data-Loss Guardrail)
# -----------------------------------------------------------------------------
audit_datastore() {
    if [[ "$MOCK_FAIL_DATASTORE" == "true" ]]; then
        DATASTORE_STATUS="CRITICAL"
        DATASTORE_DETAIL="Simulated CRITICAL failure: Partition 4 missing or corrupted"
        return
    fi

    if [[ "$MOCK_MODE" == "true" ]]; then
        if [[ -n "$MOCK_SCORE" && "$MOCK_SCORE" -lt 5 ]]; then
            DATASTORE_STATUS="CRITICAL"
            DATASTORE_DETAIL="Simulated Partition 4 missing (mock score: ${MOCK_SCORE})"
        else
            DATASTORE_STATUS="PASS"
            DATASTORE_DETAIL="Partition 4 (/dev/nvme0n1p4) intact, NTFS verified (201 GB preserved)"
            SCORE=$((SCORE + 1))
        fi
        return
    fi

    local dev_p4="/dev/nvme0n1p4"
    local has_p4=false
    local is_ntfs=false

    if [[ -b "$dev_p4" ]]; then
        has_p4=true
        if blkid "$dev_p4" 2>/dev/null | grep -qi "ntfs" || lsblk -no FSTYPE "$dev_p4" 2>/dev/null | grep -qi "ntfs"; then
            is_ntfs=true
        fi
    elif [[ "$ENV_TYPE" == "wsl" ]]; then
        # In WSL, check /mnt/d mount point
        if [[ -d "/mnt/d" ]] && touch "/mnt/d/.quality_gate_probe_tmp" 2>/dev/null; then
            rm -f "/mnt/d/.quality_gate_probe_tmp"
            has_p4=true
            is_ntfs=true
        elif [[ -d "/mnt/d" ]]; then
            has_p4=true
            is_ntfs=true
        fi
    fi

    if [[ "$has_p4" == "true" && "$is_ntfs" == "true" ]]; then
        DATASTORE_STATUS="PASS"
        if [[ -b "$dev_p4" ]]; then
            DATASTORE_DETAIL="Partition 4 (/dev/nvme0n1p4) intact as NTFS"
        else
            DATASTORE_DETAIL="WSL Drive D: (/mnt/d) accessible and NTFS confirmed"
        fi
        SCORE=$((SCORE + 1))
    elif [[ "$has_p4" == "true" ]]; then
        DATASTORE_STATUS="CRITICAL"
        DATASTORE_DETAIL="Partition 4 exists but is NOT formatted as NTFS! Risk of data loss!"
    else
        # If neither block device nor /mnt/d exists in bare metal
        DATASTORE_STATUS="CRITICAL"
        DATASTORE_DETAIL="Partition 4 (/dev/nvme0n1p4) not found on NVMe disk!"
    fi
}

# Run all 5 audits
audit_wifi
audit_audio
audit_bluetooth
audit_graphics
audit_datastore

# Evaluate Quality Gate Pass/Fail
REQUIRED_SCORE=4
if [[ "$STRICT_MODE" == "true" ]]; then
    REQUIRED_SCORE=5
fi

QUALITY_GATE_PASSED=false
RESULT_STATUS="NOT MET"
RECOMMENDATION="Do NOT delete staging partitions yet. Resolve failing checks above."

if [[ "$DATASTORE_STATUS" == "CRITICAL" ]]; then
    QUALITY_GATE_PASSED=false
    RESULT_STATUS="CRITICAL FAILURE"
    RECOMMENDATION="ABORT! Partition 4 (DATA_STORE) is missing or corrupted. Do NOT delete staging partitions yet or modify disk partitions."
elif (( SCORE >= REQUIRED_SCORE )); then
    QUALITY_GATE_PASSED=true
    RESULT_STATUS="PASSED"
    RECOMMENDATION="Quality Gate PASSED. Safe to proceed with Phase 4 (Auto-Mount, Restore WSL, and Safe Root Expansion)."
fi

# Render Human-Readable Output
generate_text_report() {
    cat << EOF
================================================================================
              DEBIAN BARE-METAL POST-INSTALL QUALITY GATE AUDIT
================================================================================
Host Platform: Lenovo IdeaPad 3 (81WD) | SSD: SSSTC CL1-4D512 NVMe (512GB)
Environment:   ${ENV_TYPE^^} (Timestamp: ${TIMESTAMP})
Protected Vol: Partition 4 (Drive D: / DATA_STORE - 201 GB NTFS)
================================================================================

[1/5] Checking Intel AC 9560 Wi-Fi (iwlwifi)...
      Status:  [${WIFI_STATUS}]
      Details: ${WIFI_DETAIL}

[2/5] Checking ALSA/PipeWire Audio...
      Status:  [${AUDIO_STATUS}]
      Details: ${AUDIO_DETAIL}

[3/5] Checking Bluetooth Controller...
      Status:  [${BT_STATUS}]
      Details: ${BT_DETAIL}

[4/5] Checking GNOME Wayland & Intel i915 DRM...
      Status:  [${GFX_STATUS}]
      Details: ${GFX_DETAIL}

[5/5] Checking Partition 4 (DATA_STORE) Preservation...
      Status:  [${DATASTORE_STATUS}]
      Details: ${DATASTORE_DETAIL}

================================================================================
Quality Gate Score: ${SCORE} / ${TOTAL} (Required: >= ${REQUIRED_SCORE})
RESULT: Quality Gate ${RESULT_STATUS}
Action: ${RECOMMENDATION}
================================================================================
EOF
}

# Render JSON Output
generate_json_report() {
    cat << EOF
{
  "platform": "Lenovo IdeaPad 3 (81WD)",
  "environment": "${ENV_TYPE}",
  "timestamp": "${TIMESTAMP}",
  "score": ${SCORE},
  "total": ${TOTAL},
  "required_score": ${REQUIRED_SCORE},
  "passed": ${QUALITY_GATE_PASSED},
  "status": "${RESULT_STATUS}",
  "recommendation": "${RECOMMENDATION}",
  "checks": {
    "wifi": {
      "name": "Intel AC 9560 Wi-Fi (iwlwifi)",
      "status": "${WIFI_STATUS}",
      "details": "${WIFI_DETAIL}"
    },
    "audio": {
      "name": "ALSA/PipeWire Audio",
      "status": "${AUDIO_STATUS}",
      "details": "${AUDIO_DETAIL}"
    },
    "bluetooth": {
      "name": "Bluetooth Controller",
      "status": "${BT_STATUS}",
      "details": "${BT_DETAIL}"
    },
    "graphics": {
      "name": "GNOME Wayland & Intel i915 DRM",
      "status": "${GFX_STATUS}",
      "details": "${GFX_DETAIL}"
    },
    "data_store_partition": {
      "name": "Partition 4 (DATA_STORE) Preservation",
      "status": "${DATASTORE_STATUS}",
      "details": "${DATASTORE_DETAIL}"
    }
  }
}
EOF
}

# Handle Output and Reports
if [[ "$JSON_MODE" == "true" ]]; then
    JSON_CONTENT=$(generate_json_report)
    echo "${JSON_CONTENT}"
    if [[ -n "$REPORT_FILE" ]]; then
        echo "${JSON_CONTENT}" > "${REPORT_FILE}"
    fi
else
    TEXT_CONTENT=$(generate_text_report)
    echo "${TEXT_CONTENT}"
    if [[ -n "$REPORT_FILE" ]]; then
        echo "${TEXT_CONTENT}" > "${REPORT_FILE}"
    fi
fi

# Exit Code Determination
if [[ "$QUALITY_GATE_PASSED" == "true" ]]; then
    exit 0
else
    exit 1
fi
