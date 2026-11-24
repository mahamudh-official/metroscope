#!/usr/bin/env bash
# ==============================================================================
# MetroScope — Production Rollback Script
# Target: AWS EC2 t3.small, Docker Compose
# Deployment Path: /srv/metroscope/app
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
ENV_FILE="${PROJECT_ROOT}/.env"
VERSION_HISTORY_FILE="${PROJECT_ROOT}/.last_deployed_version"
ROLLBACK_LOG="${PROJECT_ROOT}/rollback.log"

# Determine Docker Command
DOCKER_CMD="docker"
if command -v sudo >/dev/null 2>&1 && ! docker info >/dev/null 2>&1; then
    DOCKER_CMD="sudo docker"
fi

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

if [[ "${TARGET_ROLLBACK_TAG}" == "latest" || ! "${TARGET_ROLLBACK_TAG}" =~ ^[0-9a-fA-F]{7,40}$ ]]; then
    log "ERROR" "Invalid rollback tag '${TARGET_ROLLBACK_TAG}'. Must be a valid 7 to 40 character hexadecimal Git SHA."
    exit 1
fi

TARGET_ROLLBACK_TAG="$(echo "${TARGET_ROLLBACK_TAG}" | tr '[:upper:]' '[:lower:]')"
export IMAGE_TAG="${TARGET_ROLLBACK_TAG}"

log "INFO" "Rolling back to verified immutable image release tag: ${TARGET_ROLLBACK_TAG}"

# Load environment
if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

# 2. Pull / Verify Target Rollback Images (Core services only)
log "INFO" "Ensuring rollback images are pulled..."
IMAGE_TAG="${TARGET_ROLLBACK_TAG}" ${DOCKER_CMD} compose -f "${COMPOSE_FILE}" pull backend frontend nginx || {
    log "WARNING" "Pulling rollback images from registry failed. Attempting to use locally cached images..."
}

# 3. Restart Core Application Containers with Rollback Image Tag (Worker excluded)
log "INFO" "Recreating core application containers with rollback tag '${TARGET_ROLLBACK_TAG}'..."
IMAGE_TAG="${TARGET_ROLLBACK_TAG}" ${DOCKER_CMD} compose -f "${COMPOSE_FILE}" up -d --remove-orphans backend frontend nginx

# 4. Verify Health After Rollback (Service-Aware Network Probes)
log "INFO" "Verifying application health post-rollback..."
HEALTHY=false

for attempt in {1..20}; do
    BACKEND_STATUS="$(${DOCKER_CMD} compose -f "${COMPOSE_FILE}" exec -T backend curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health/ready 2>/dev/null || true)"
    FRONTEND_STATUS="$(${DOCKER_CMD} compose -f "${COMPOSE_FILE}" exec -T frontend wget -q -O /dev/null --spider http://127.0.0.1:3000/ 2>/dev/null && echo "200" || true)"
    NGINX_STATUS="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/health 2>/dev/null || true)"

    log "INFO" "Rollback health check ${attempt}/20 — Backend: ${BACKEND_STATUS:-failed}, Frontend: ${FRONTEND_STATUS:-failed}, Nginx: ${NGINX_STATUS:-failed}"

    if [[ "${BACKEND_STATUS}" == "200" && "${FRONTEND_STATUS}" == "200" && "${NGINX_STATUS}" == "200" ]]; then
        HEALTHY=true
        break
    fi
    sleep 3
done

if [[ "${HEALTHY}" != "true" ]]; then
    log "ERROR" "CRITICAL: Rollback health verification failed! Check container logs via '${DOCKER_CMD} compose -f ${COMPOSE_FILE} logs'."
    exit 1
fi

log "INFO" "=================================================================="
log "INFO" "MetroScope Rollback to '${TARGET_ROLLBACK_TAG}' Completed Successfully."
log "INFO" "=================================================================="
exit 0
