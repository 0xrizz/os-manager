#!/usr/bin/env bash
# scripts/install_spotify.sh - Cryptographically verified Spotify installer for Debian/Ubuntu
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Official Spotify Linux signing key metadata (from https://www.spotify.com/us/download/linux/)
KEY_URL="https://download.spotify.com/debian/pubkey_5384CE82BA52C83A.asc"
EXPECTED_FINGERPRINT="E1096BCBFF6D418796DE78515384CE82BA52C83A"

KEYRING_DIR="/etc/apt/keyrings"
KEYRING_FILE="${KEYRING_DIR}/spotify.gpg"
SOURCES_DIR="/etc/apt/sources.list.d"
SOURCES_FILE="${SOURCES_DIR}/spotify.list"

DRY_RUN=false
CHECK_ONLY=false

show_help() {
    cat <<HELP
Usage: $(basename "$0") [OPTIONS]

Install and configure official Spotify Desktop client on Debian/Ubuntu with GPG signature verification.

Options:
  --check       Check whether Spotify is installed and configured correctly
  --dry-run     Display operations without writing files or running package managers
  -h, --help    Show this help message and exit
HELP
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --check)
            CHECK_ONLY=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown option '$1'" >&2
            show_help >&2
            exit 1
            ;;
    esac
done

check_prerequisites() {
    local missing=()
    if ! command -v curl &>/dev/null && ! command -v wget &>/dev/null; then
        missing+=("curl")
    fi
    for tool in gpg dpkg; do
        if ! command -v "${tool}" &>/dev/null; then
            missing+=("${tool}")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        if [ "${DRY_RUN}" = true ]; then
            echo "[DRY RUN] Would install missing prerequisites: ${missing[*]}"
        else
            echo "==> Installing missing prerequisites: ${missing[*]}..."
            sudo apt update && sudo apt install -y "${missing[@]}"
        fi
    fi
}

download_file() {
    local url="$1"
    local dest="$2"
    if command -v curl &>/dev/null; then
        curl -fsSL -o "${dest}" "${url}"
    elif command -v wget &>/dev/null; then
        wget -nv -O "${dest}" "${url}"
    else
        echo "Error: Neither curl nor wget is available." >&2
        return 1
    fi
}

verify_key_fingerprint() {
    local asc_file="$1"
    local computed_fp
    computed_fp="$(gpg --show-keys --with-colons "${asc_file}" 2>/dev/null | awk -F: '$1=="fpr"{print $10; exit}')"

    if [ "${computed_fp}" != "${EXPECTED_FINGERPRINT}" ]; then
        echo "Error: Key fingerprint mismatch!" >&2
        echo "  Expected: ${EXPECTED_FINGERPRINT}" >&2
        echo "  Actual:   ${computed_fp}" >&2
        return 1
    fi

    echo "==> Key fingerprint verified: ${computed_fp}"
    return 0
}

check_installed() {
    local status=0
    echo "=== Checking Spotify Installation Status ==="

    if command -v spotify &>/dev/null; then
        echo "  [PASS] spotify executable found: $(which spotify)"
    else
        echo "  [FAIL] spotify executable not found in PATH"
        status=1
    fi

    if [ -f "${KEYRING_FILE}" ] || [ -f "/etc/apt/trusted.gpg.d/spotify.gpg" ]; then
        echo "  [PASS] Spotify keyring file present"
    else
        echo "  [FAIL] Keyring file missing (${KEYRING_FILE})"
        status=1
    fi

    if [ -f "${SOURCES_FILE}" ]; then
        echo "  [PASS] APT sources list present: ${SOURCES_FILE}"
    else
        echo "  [FAIL] APT sources list missing: ${SOURCES_FILE}"
        status=1
    fi

    return "${status}"
}

install_spotify() {
    echo "=== Installing Spotify for Linux ==="
    check_prerequisites

    local repo_line="deb [signed-by=${KEYRING_FILE}] https://repository.spotify.com stable non-free"

    local tmp_asc
    local tmp_gpg
    tmp_asc="$(mktemp --suffix=.asc)"
    tmp_gpg="$(mktemp --suffix=.gpg)"
    # shellcheck disable=SC2064
    trap "rm -f '${tmp_asc}' '${tmp_gpg}'" EXIT

    echo "==> [1/4] Downloading official Spotify public key..."
    if [ "${DRY_RUN}" = true ]; then
        echo "[DRY RUN] curl -fsSL -o ${tmp_asc} ${KEY_URL}"
        echo "[DRY RUN] gpg --dearmor -o ${tmp_gpg} ${tmp_asc}"
        echo "[DRY RUN] sudo mkdir -p -m 755 ${KEYRING_DIR}"
        echo "[DRY RUN] sudo cp ${tmp_gpg} ${KEYRING_FILE}"
        echo "[DRY RUN] sudo chmod 644 ${KEYRING_FILE}"
        echo "[DRY RUN] sudo mkdir -p -m 755 ${SOURCES_DIR}"
        echo "[DRY RUN] echo '${repo_line}' | sudo tee ${SOURCES_FILE}"
        echo "[DRY RUN] sudo apt update && sudo apt install -y spotify-client"
        return 0
    fi

    download_file "${KEY_URL}" "${tmp_asc}"
    verify_key_fingerprint "${tmp_asc}"

    echo "==> [2/4] Armoring & installing keyring to ${KEYRING_FILE}..."
    gpg --dearmor --yes -o "${tmp_gpg}" "${tmp_asc}"

    sudo mkdir -p -m 755 "${KEYRING_DIR}"
    sudo cp "${tmp_gpg}" "${KEYRING_FILE}"
    sudo chmod 644 "${KEYRING_FILE}"

    echo "==> [3/4] Configuring APT sources list at ${SOURCES_FILE}..."
    sudo mkdir -p -m 755 "${SOURCES_DIR}"
    echo "${repo_line}" | sudo tee "${SOURCES_FILE}" > /dev/null
    sudo chmod 644 "${SOURCES_FILE}"

    echo "==> [4/4] Updating package list and installing spotify-client..."
    sudo apt update
    sudo apt install -y spotify-client

    echo "=== Installation complete ==="
    which spotify
}

if [ "${CHECK_ONLY}" = true ]; then
    check_installed
    exit $?
else
    install_spotify
fi
