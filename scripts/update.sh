#!/usr/bin/env bash
set -Eeuo pipefail

SERVICE_NAME="${BIRDMESH_SERVICE_NAME:-birdmesh.service}"
ENV_FILE="${BIRDMESH_ENV_FILE:-/etc/birdmesh.env}"
PROJECT_ROOT="${BIRDMESH_PROJECT_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
VENV="${BIRDMESH_VENV:-${PROJECT_ROOT}/.venv}"

if [[ ${EUID} -ne 0 ]]; then
    echo "Run this update with sudo: sudo ${PROJECT_ROOT}/scripts/update.sh" >&2
    exit 1
fi

if [[ ! -x "${VENV}/bin/python" || ! -x "${VENV}/bin/birdmesh" ]]; then
    echo "BirdMesh virtualenv not found at ${VENV}" >&2
    exit 1
fi

if [[ ! -r "${ENV_FILE}" ]]; then
    echo "BirdMesh environment file is not readable: ${ENV_FILE}" >&2
    exit 1
fi

SERVICE_USER="${BIRDMESH_SERVICE_USER:-$(systemctl show --property=User --value "${SERVICE_NAME}")}"
if [[ -z "${SERVICE_USER}" ]]; then
    echo "Could not determine the user for ${SERVICE_NAME}" >&2
    exit 1
fi

restart_service() {
    local update_status=$?
    trap - EXIT
    echo "Restarting ${SERVICE_NAME}..."
    if ! systemctl restart "${SERVICE_NAME}"; then
        echo "ERROR: ${SERVICE_NAME} could not be restarted." >&2
        exit 1
    fi
    exit "${update_status}"
}

# Install and validate while the daemon has released an exclusive serial device.
trap restart_service EXIT
echo "Stopping ${SERVICE_NAME}..."
systemctl stop "${SERVICE_NAME}"

echo "Reinstalling BirdMesh into ${VENV}..."
runuser --user "${SERVICE_USER}" -- \
    "${VENV}/bin/python" -m pip install --force-reinstall --no-deps "${PROJECT_ROOT}"

echo "Validating BirdNET and Meshtastic connectivity..."
"${VENV}/bin/birdmesh" --env-file "${ENV_FILE}" check

echo "BirdMesh update validated successfully."
