#!/usr/bin/env bash
# ==============================================================================
# MetroScope — Production Rollback Script
# Target: AWS EC2 t3.small, Docker Compose
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
ENV_FILE="${PROJECT_ROOT}/.env"
VERSION_HISTORY_FILE="${PROJECT_ROOT}/.last_deployed_version"
ROLLBACK_LOG="${PROJECT_ROOT}/rollback.log"

log() {
    local level="$1"
    local message="$2"
    local ts
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "[${ts}] [${level}] ${message}" | tee -a "${ROLLBACK_LOG}"
}

log "WARNING" "=================================================================="
log "WARNING" "Starting MetroScope Emergency Rollback Procedure..."
log "WARNING" "=================================================================="

# 1. Determine Rollback Target Tag
TARGET_ROLLBACK_TAG="${1:-}"

if [[ -z "${TARGET_ROLLBACK_TAG}" ]]; then
    if [[ -f "${VERSION_HISTORY_FILE}" ]]; then
        TARGET_ROLLBACK_TAG="$(cat "${VERSION_HISTORY_FILE}")"
    else
        log "ERROR" "No target rollback tag provided and ${VERSION_HISTORY_FILE} does not exist."
        exit 1
    fi
fi

log "INFO" "Rolling back to verified image release tag: ${TARGET_ROLLBACK_TAG}"

# Load environment
if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

# 2. Pull / Verify Target Rollback Images
log "INFO" "Ensuring rollback images are pulled..."
IMAGE_TAG="${TARGET_ROLLBACK_TAG}" docker compose -f "${COMPOSE_FILE}" pull backend worker frontend || {
    log "WARNING" "Pulling rollback images from registry failed. Attempting to use locally cached images..."
}

# 3. Restart Application Containers with Rollback Image Tag
log "INFO" "Recreating application containers with rollback tag '${TARGET_ROLLBACK_TAG}'..."
IMAGE_TAG="${TARGET_ROLLBACK_TAG}" docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans backend worker frontend nginx

# 4. Verify Health After Rollback
log "INFO" "Verifying application health post-rollback..."
HEALTHY=false

for attempt in {1..20}; do
    BACKEND_CODE="$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/ready || true)"
    FRONTEND_CODE="$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ || true)"

    log "INFO" "Rollback health check ${attempt}/20 - Backend: ${BACKEND_CODE}, Frontend: ${FRONTEND_CODE}"

    if [[ "${BACKEND_CODE}" == "200" && "${FRONTEND_CODE}" == "200" ]]; then
        HEALTHY=true
        break
    fi
    sleep 3
done

if [[ "${HEALTHY}" != "true" ]]; then
    log "ERROR" "CRITICAL: Rollback health verification failed! Check container logs via 'docker compose -f docker-compose.prod.yml logs'."
    exit 1
fi

log "INFO" "=================================================================="
log "INFO" "MetroScope Rollback to '${TARGET_ROLLBACK_TAG}' Completed Successfully."
log "INFO" "=================================================================="
exit 0
