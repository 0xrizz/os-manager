#!/usr/bin/env bash
# scripts/install_github_cli.sh - Cryptographically verified GitHub CLI installer for Debian/Ubuntu
set -euo pipefail

WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Official GitHub CLI signing metadata (from https://github.com/cli/cli/blob/trunk/docs/install_linux.md)
KEYRING_URL="https://cli.github.com/packages/githubcli-archive-keyring.gpg"
EXPECTED_SHA256="6084d5d7bd8e288441e0e94fc6275570895da18e6751f70f057485dc2d1a811b"
EXPECTED_FINGERPRINTS=(
    "2C6106201985B60E6C7AC87323F3D4EA75716059"
    "7F38BBB59D064DBCB3D84D725612B36462313325"
)

KEYRING_DIR="/etc/apt/keyrings"
KEYRING_FILE="${KEYRING_DIR}/githubcli-archive-keyring.gpg"
SOURCES_DIR="/etc/apt/sources.list.d"
SOURCES_FILE="${SOURCES_DIR}/github-cli.list"

DRY_RUN=false
CHECK_ONLY=false

show_help() {
    cat <<HELP
Usage: $(basename "$0") [OPTIONS]

Install and configure official GitHub CLI (gh) on Debian/Ubuntu with checksum verification.

Options:
  --check       Check whether GitHub CLI is installed and configured correctly
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
        missing+=("wget")
    fi
    for tool in gpg dpkg sha256sum; do
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

verify_keyring_content() {
    local key_file="$1"
    local computed_sha
    computed_sha="$(sha256sum "${key_file}" | awk '{print $1}')"

    if [ "${computed_sha}" != "${EXPECTED_SHA256}" ]; then
        echo "Error: Checksum mismatch for keyring!" >&2
        echo "  Expected: ${EXPECTED_SHA256}" >&2
        echo "  Actual:   ${computed_sha}" >&2
        return 1
    fi

    echo "==> Checksum verified successfully: ${computed_sha}"
    return 0
}

check_installed() {
    local status=0
    echo "=== Checking GitHub CLI Installation Status ==="

    if command -v gh &>/dev/null; then
        local version
        version="$(gh --version | head -n 1)"
        echo "  [PASS] gh executable found: ${version}"
    else
        echo "  [FAIL] gh executable not found in PATH"
        status=1
    fi

    if [ -f "${KEYRING_FILE}" ]; then
        echo "  [PASS] Keyring file present: ${KEYRING_FILE}"
        if verify_keyring_content "${KEYRING_FILE}" >/dev/null 2>&1; then
            echo "  [PASS] Keyring SHA256 matches official release"
        else
            echo "  [WARN] Keyring SHA256 does not match official expected hash"
        fi
    else
        echo "  [FAIL] Keyring file missing: ${KEYRING_FILE}"
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

install_gh() {
    echo "=== Installing GitHub CLI for Debian/Ubuntu ==="
    check_prerequisites

    local arch
    arch="$(dpkg --print-architecture)"
    local repo_line="deb [arch=${arch} signed-by=${KEYRING_FILE}] https://cli.github.com/packages stable main"

    local tmp_key
    tmp_key="$(mktemp)"
    # shellcheck disable=SC2064
    trap "rm -f '${tmp_key}'" EXIT

    echo "==> [1/4] Downloading official keyring..."
    if [ "${DRY_RUN}" = true ]; then
        echo "[DRY RUN] curl -fsSL -o ${tmp_key} ${KEYRING_URL}"
        echo "[DRY RUN] Verify SHA256 matches ${EXPECTED_SHA256}"
        echo "[DRY RUN] sudo mkdir -p -m 755 ${KEYRING_DIR}"
        echo "[DRY RUN] sudo cp ${tmp_key} ${KEYRING_FILE}"
        echo "[DRY RUN] sudo chmod go+r ${KEYRING_FILE}"
        echo "[DRY RUN] sudo mkdir -p -m 755 ${SOURCES_DIR}"
        echo "[DRY RUN] echo '${repo_line}' | sudo tee ${SOURCES_FILE}"
        echo "[DRY RUN] sudo apt update && sudo apt install -y gh"
        return 0
    fi

    download_file "${KEYRING_URL}" "${tmp_key}"
    verify_keyring_content "${tmp_key}"

    echo "==> [2/4] Installing keyring to ${KEYRING_FILE}..."
    sudo mkdir -p -m 755 "${KEYRING_DIR}"
    sudo cp "${tmp_key}" "${KEYRING_FILE}"
    sudo chmod 644 "${KEYRING_FILE}"

    echo "==> [3/4] Configuring APT sources list at ${SOURCES_FILE}..."
    sudo mkdir -p -m 755 "${SOURCES_DIR}"
    echo "${repo_line}" | sudo tee "${SOURCES_FILE}" > /dev/null
    sudo chmod 644 "${SOURCES_FILE}"

    echo "==> [4/4] Updating package index and installing gh..."
    sudo apt update
    sudo apt install -y gh

    echo "=== Installation complete ==="
    gh --version | head -n 1
}

if [ "${CHECK_ONLY}" = true ]; then
    check_installed
    exit $?
else
    install_gh
fi
