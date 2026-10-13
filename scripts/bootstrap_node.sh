#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="${ROOT_DIR}/.tools"
NODE_DIR="${TOOLS_DIR}/node"
NODE_VERSION="${NODE_VERSION:-v26.5.0}"

if [[ -x "${NODE_DIR}/bin/node" ]]; then
  "${NODE_DIR}/bin/node" --version
  exit 0
fi

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) PLATFORM="darwin-arm64" ;;
  Darwin-x86_64) PLATFORM="darwin-x64" ;;
  Linux-x86_64) PLATFORM="linux-x64" ;;
  Linux-aarch64|Linux-arm64) PLATFORM="linux-arm64" ;;
  *)
    echo "Unsupported platform: $(uname -s)-$(uname -m). Install Node.js 20+ manually." >&2
    exit 1
    ;;
esac

ARCHIVE="node-${NODE_VERSION}-${PLATFORM}.tar.gz"
BASE_URL="https://nodejs.org/dist/${NODE_VERSION}"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TEMP_DIR}"' EXIT

echo "Downloading Node.js ${NODE_VERSION} for ${PLATFORM}..."
curl -fsSL "${BASE_URL}/${ARCHIVE}" -o "${TEMP_DIR}/${ARCHIVE}"
curl -fsSL "${BASE_URL}/SHASUMS256.txt" -o "${TEMP_DIR}/SHASUMS256.txt"

EXPECTED="$(awk -v filename="${ARCHIVE}" '$2 == filename { print $1 }' "${TEMP_DIR}/SHASUMS256.txt")"
if [[ -z "${EXPECTED}" ]]; then
  echo "Could not find checksum for ${ARCHIVE}." >&2
  exit 1
fi

if command -v shasum >/dev/null 2>&1; then
  ACTUAL="$(shasum -a 256 "${TEMP_DIR}/${ARCHIVE}" | awk '{ print $1 }')"
else
  ACTUAL="$(sha256sum "${TEMP_DIR}/${ARCHIVE}" | awk '{ print $1 }')"
fi

if [[ "${EXPECTED}" != "${ACTUAL}" ]]; then
  echo "Checksum verification failed for ${ARCHIVE}." >&2
  exit 1
fi

mkdir -p "${TOOLS_DIR}"
tar -xzf "${TEMP_DIR}/${ARCHIVE}" -C "${TOOLS_DIR}"
rm -rf "${NODE_DIR}"
mv "${TOOLS_DIR}/node-${NODE_VERSION}-${PLATFORM}" "${NODE_DIR}"

echo "Installed Node.js $(${NODE_DIR}/bin/node --version) at ${NODE_DIR}"
