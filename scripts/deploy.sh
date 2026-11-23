#!/usr/bin/env bash
# ==============================================================================
# MetroScope — Production Deployment Script
# Target: AWS EC2 t3.small (Ubuntu 24.04 LTS), Docker Compose
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
ENV_FILE="${PROJECT_ROOT}/.env"
VERSION_HISTORY_FILE="${PROJECT_ROOT}/.last_deployed_version"
DEPLOY_LOG="${PROJECT_ROOT}/deploy.log"

log() {
    local level="$1"
    local message="$2"
    local ts
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "[${ts}] [${level}] ${message}" | tee -a "${DEPLOY_LOG}"
}

log "INFO" "=================================================================="
log "INFO" "Starting MetroScope production deployment..."
log "INFO" "=================================================================="

# 1. Environment Verification
if [[ ! -f "${ENV_FILE}" ]]; then
    log "ERROR" "Production environment file (.env) not found at ${ENV_FILE}."
    log "ERROR" "Copy .env.production.template to .env and configure strong production secrets."
    exit 1
fi

# Load environment
set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

# Determine Target Image Tag
TARGET_IMAGE_TAG="${IMAGE_TAG:-latest}"
log "INFO" "Target Deployment Image Tag: ${TARGET_IMAGE_TAG}"

# 2. Record Prior Version for Instant Rollback
if [[ -f "${VERSION_HISTORY_FILE}" ]]; then
    PREVIOUS_IMAGE_TAG="$(cat "${VERSION_HISTORY_FILE}")"
    log "INFO" "Previous deployed image tag was: ${PREVIOUS_IMAGE_TAG}"
else
    PREVIOUS_IMAGE_TAG="${TARGET_IMAGE_TAG}"
fi

# 3. Docker Compose Configuration Validation
log "INFO" "Validating Docker Compose production configuration..."
if ! docker compose -f "${COMPOSE_FILE}" config -q; then
    log "ERROR" "Docker compose validation failed. Check syntax and environment variables."
    exit 1
fi
log "INFO" "Docker Compose configuration is valid."

# 4. Authenticate with GitHub Container Registry (if credentials available)
if [[ -n "${GHCR_TOKEN:-}" && -n "${GHCR_USER:-}" ]]; then
    log "INFO" "Authenticating with GitHub Container Registry (${GHCR_REGISTRY:-ghcr.io})..."
    echo "${GHCR_TOKEN}" | docker login "${GHCR_REGISTRY:-ghcr.io}" -u "${GHCR_USER}" --password-stdin
fi

# 5. Pull Approved Production Images
log "INFO" "Pulling production images for tag '${TARGET_IMAGE_TAG}'..."
IMAGE_TAG="${TARGET_IMAGE_TAG}" docker compose -f "${COMPOSE_FILE}" pull backend worker frontend

# 6. Ensure Database Service is Running and Healthy
log "INFO" "Ensuring database service is running and healthy..."
docker compose -f "${COMPOSE_FILE}" up -d db

log "INFO" "Waiting for database to report healthy status..."
for attempt in {1..30}; do
    DB_STATUS="$(docker compose -f "${COMPOSE_FILE}" ps db --format '{{.Health}}' 2>/dev/null || true)"
    if [[ "${DB_STATUS}" == *"healthy"* ]]; then
        log "INFO" "PostgreSQL is healthy (attempt ${attempt}/30)."
        break
    fi
    sleep 2
    if [[ "${attempt}" -eq 30 ]]; then
        log "ERROR" "Timed out waiting for PostgreSQL to become healthy."
        exit 1
    fi
done

# 7. Safe Database Migration (One-off container execution)
log "INFO" "Running Alembic migrations sequentially via one-off backend container..."
if ! docker compose -f "${COMPOSE_FILE}" run --rm backend alembic upgrade head; then
    log "ERROR" "Database migration failed! Halting deployment."
    exit 1
fi
log "INFO" "Database migrations successfully applied."

# 8. Start / Rolling Update of Application Containers
log "INFO" "Starting application services (backend, worker, frontend, nginx)..."
IMAGE_TAG="${TARGET_IMAGE_TAG}" docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans backend worker frontend nginx

# 9. Post-Deployment Readiness & Health Verification
log "INFO" "Verifying application readiness..."
HEALTHY=false

for attempt in {1..20}; do
    # Probe backend readiness endpoint
    BACKEND_CODE="$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/ready || true)"
    # Probe frontend HTTP response
    FRONTEND_CODE="$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/ || true)"

    log "INFO" "Health probe attempt ${attempt}/20 - Backend: ${BACKEND_CODE}, Frontend: ${FRONTEND_CODE}"

    if [[ "${BACKEND_CODE}" == "200" && "${FRONTEND_CODE}" == "200" ]]; then
        HEALTHY=true
        break
    fi
    sleep 3
done

if [[ "${HEALTHY}" != "true" ]]; then
    log "ERROR" "Post-deployment health checks failed! Initiating automated rollback..."
    if [[ -x "${SCRIPT_DIR}/rollback.sh" ]]; then
        "${SCRIPT_DIR}/rollback.sh" "${PREVIOUS_IMAGE_TAG}"
    else
        log "ERROR" "Rollback script not found at ${SCRIPT_DIR}/rollback.sh."
    fi
    exit 1
fi

# 10. Record Successful Release Tag
echo "${TARGET_IMAGE_TAG}" > "${VERSION_HISTORY_FILE}"
log "INFO" "Release '${TARGET_IMAGE_TAG}' successfully verified and recorded."
log "INFO" "=================================================================="
log "INFO" "MetroScope Production Deployment Completed Successfully."
log "INFO" "=================================================================="
exit 0
