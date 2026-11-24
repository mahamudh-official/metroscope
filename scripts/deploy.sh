#!/usr/bin/env bash
# ==============================================================================
# MetroScope — Production Deployment Script
# Target: AWS EC2 t3.small (Ubuntu 24.04 LTS, ap-southeast-2), Docker Compose
# Deployment Path: /srv/metroscope/app
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
ENV_FILE="${PROJECT_ROOT}/.env"
VERSION_HISTORY_FILE="${PROJECT_ROOT}/.last_deployed_version"
DEPLOY_LOG="${PROJECT_ROOT}/deploy.log"

# Determine Docker Command (support running without sudo if in docker group, or with sudo)
DOCKER_CMD="docker"
if command -v sudo >/dev/null 2>&1 && ! docker info >/dev/null 2>&1; then
    DOCKER_CMD="sudo docker"
fi

log() {
    local level="$1"
    local message="$2"
    local ts
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "[${ts}] [${level}] ${message}" | tee -a "${DEPLOY_LOG}"
}

log "INFO" "=================================================================="
log "INFO" "Starting MetroScope production deployment..."
log "INFO" "Deployment Directory: ${PROJECT_ROOT}"
log "INFO" "Docker Command: ${DOCKER_CMD}"
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

# Determine Target Image Tag and Registry
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
if ! ${DOCKER_CMD} compose -f "${COMPOSE_FILE}" config -q; then
    log "ERROR" "Docker compose validation failed. Check syntax and environment variables."
    exit 1
fi
log "INFO" "Docker Compose configuration is valid."

# 4. Authenticate with GitHub Container Registry (if credentials provided)
if [[ -n "${GHCR_TOKEN:-}" && -n "${GHCR_USER:-}" ]]; then
    log "INFO" "Authenticating with GitHub Container Registry (${GHCR_REGISTRY:-ghcr.io})..."
    echo "${GHCR_TOKEN}" | ${DOCKER_CMD} login "${GHCR_REGISTRY:-ghcr.io}" -u "${GHCR_USER}" --password-stdin
fi

# 5. Pull Approved Production Images (Core services only; worker excluded from initial deployment)
log "INFO" "Pulling production images for tag '${TARGET_IMAGE_TAG}'..."
IMAGE_TAG="${TARGET_IMAGE_TAG}" ${DOCKER_CMD} compose -f "${COMPOSE_FILE}" pull backend frontend nginx db

# 6. Ensure Database Service is Running and Healthy
log "INFO" "Starting database service (PostgreSQL 16 Alpine)..."
${DOCKER_CMD} compose -f "${COMPOSE_FILE}" up -d db

log "INFO" "Waiting for database to report healthy status..."
DB_HEALTHY=false
for attempt in {1..30}; do
    DB_STATUS="$(${DOCKER_CMD} compose -f "${COMPOSE_FILE}" ps db --format '{{.Health}}' 2>/dev/null || true)"
    if [[ "${DB_STATUS}" == *"healthy"* ]]; then
        log "INFO" "PostgreSQL is healthy (attempt ${attempt}/30)."
        DB_HEALTHY=true
        break
    fi
    sleep 2
done

if [[ "${DB_HEALTHY}" != "true" ]]; then
    log "ERROR" "PostgreSQL failed to report healthy status within 60 seconds."
    log "ERROR" "Container logs:"
    ${DOCKER_CMD} compose -f "${COMPOSE_FILE}" logs --tail 50 db | tee -a "${DEPLOY_LOG}"
    exit 1
fi

# 7. Safe Database Migration (One-off container execution)
log "INFO" "Running Alembic migrations sequentially via one-off backend container..."
if ! ${DOCKER_CMD} compose -f "${COMPOSE_FILE}" run --rm backend alembic upgrade head; then
    log "ERROR" "Database migration failed! Halting deployment to protect schema integrity."
    exit 1
fi
log "INFO" "Database migrations successfully applied."

# 8. Start Application Services (backend, frontend, nginx ONLY; worker is explicitly NOT started)
log "INFO" "Starting core application services (backend, frontend, nginx)..."
IMAGE_TAG="${TARGET_IMAGE_TAG}" ${DOCKER_CMD} compose -f "${COMPOSE_FILE}" up -d --remove-orphans backend frontend nginx

# 9. Service-Aware Health & Readiness Verification
log "INFO" "Verifying application service health across internal Docker network..."
HEALTHY=false
FAILING_SERVICE=""

for attempt in {1..25}; do
    # 9a. Verify Backend Readiness Probe via internal container network
    BACKEND_STATUS="$(${DOCKER_CMD} compose -f "${COMPOSE_FILE}" exec -T backend curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health/ready 2>/dev/null || true)"
    
    # 9b. Verify Frontend HTTP Response via internal container network
    FRONTEND_STATUS="$(${DOCKER_CMD} compose -f "${COMPOSE_FILE}" exec -T frontend wget -q -O /dev/null --spider http://127.0.0.1:3000/ 2>/dev/null && echo "200" || true)"
    
    # 9c. Verify Nginx Health Endpoint via exposed port 80
    NGINX_STATUS="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/health 2>/dev/null || true)"

    log "INFO" "Health probe attempt ${attempt}/25 — Backend: ${BACKEND_STATUS:-failed}, Frontend: ${FRONTEND_STATUS:-failed}, Nginx: ${NGINX_STATUS:-failed}"

    if [[ "${BACKEND_STATUS}" == "200" && "${FRONTEND_STATUS}" == "200" && "${NGINX_STATUS}" == "200" ]]; then
        HEALTHY=true
        break
    fi

    if [[ "${BACKEND_STATUS}" != "200" ]]; then
        FAILING_SERVICE="backend"
    elif [[ "${FRONTEND_STATUS}" != "200" ]]; then
        FAILING_SERVICE="frontend"
    elif [[ "${NGINX_STATUS}" != "200" ]]; then
        FAILING_SERVICE="nginx"
    fi

    sleep 3
done

if [[ "${HEALTHY}" != "true" ]]; then
    log "ERROR" "Post-deployment health checks failed! Failing service identified: ${FAILING_SERVICE}"
    log "ERROR" "Capturing logs for ${FAILING_SERVICE}..."
    ${DOCKER_CMD} compose -f "${COMPOSE_FILE}" logs --tail 50 "${FAILING_SERVICE}" | tee -a "${DEPLOY_LOG}"
    
    log "WARNING" "Initiating automated rollback to previous release tag: ${PREVIOUS_IMAGE_TAG}..."
    if [[ -x "${SCRIPT_DIR}/rollback.sh" ]]; then
        "${SCRIPT_DIR}/rollback.sh" "${PREVIOUS_IMAGE_TAG}"
    else
        log "ERROR" "Rollback script not executable at ${SCRIPT_DIR}/rollback.sh."
    fi
    exit 1
fi

# 10. Record Successful Release Tag
echo "${TARGET_IMAGE_TAG}" > "${VERSION_HISTORY_FILE}"
log "INFO" "Release '${TARGET_IMAGE_TAG}' successfully verified and recorded."
log "INFO" "=================================================================="
log "INFO" "MetroScope Production Deployment Completed Successfully."
log "INFO" "Verified: PostgreSQL healthy, Backend ready, Frontend online, Nginx proxying."
log "INFO" "Background worker service remained stopped (safe initial deployment policy)."
log "INFO" "=================================================================="
exit 0
