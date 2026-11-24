#!/usr/bin/env bash
# ==============================================================================
# MetroScope — Production Deployment Validation Diagnostic Script
# Target: AWS EC2 t3.small, Docker Compose
# Deployment Path: /srv/metroscope/app
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
if [[ ! -f "${COMPOSE_FILE}" ]]; then
    COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
fi

# Determine Docker Command
DOCKER_CMD="docker"
if command -v sudo >/dev/null 2>&1 && ! docker info >/dev/null 2>&1; then
    DOCKER_CMD="sudo docker"
fi

# Load environment if present
ENV_FILE="${PROJECT_ROOT}/.env"
if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

echo "=============================================================================="
echo "          METROSCOPE PRODUCTION DEPLOYMENT VALIDATION REPORT                  "
echo "=============================================================================="
echo "Timestamp:   $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "Host:        $(hostname)"
echo "Directory:   ${PROJECT_ROOT}"
echo "Compose:     ${COMPOSE_FILE}"
echo "Docker Cmd:  ${DOCKER_CMD}"
echo "=============================================================================="

PASS_COUNT=0
FAIL_COUNT=0

check_step() {
    local name="$1"
    local command="$2"
    echo -n "[CHECK] ${name}... "
    if eval "${command}" > /dev/null 2>&1; then
        echo "PASSED"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "FAILED"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

# 1. Docker Daemon & CLI
check_step "Docker daemon operational" "${DOCKER_CMD} info"
check_step "Docker Compose v2 available" "${DOCKER_CMD} compose version"

# 2. Environment Configuration
check_step "Environment file (.env) exists" "[[ -f '${PROJECT_ROOT}/.env' ]]"
check_step "Docker Compose config valid" "${DOCKER_CMD} compose -f '${COMPOSE_FILE}' config -q"

# 3. Persistent Storage
check_step "PostgreSQL persistent storage configured" "[[ -d '${POSTGRES_DATA_DIR:-/srv/metroscope/data/postgres}' ]] || ${DOCKER_CMD} volume ls | grep -E 'postgres_data|metroscope.*postgres'"

# 4. Container Runtime Health
echo ""
echo "--- Running Container Status & Health ---"
${DOCKER_CMD} compose -f "${COMPOSE_FILE}" ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}\t{{.Ports}}" || true

echo ""
echo "--- Service-Aware Network Probes ---"
# 5. Service Endpoints (Internal Network Probes)
check_step "FastAPI Liveness Probe (container:8000/health/live)" \
    "${DOCKER_CMD} compose -f '${COMPOSE_FILE}' exec -T backend curl -sf http://127.0.0.1:8000/health/live"

check_step "FastAPI Readiness Probe (container:8000/health/ready)" \
    "${DOCKER_CMD} compose -f '${COMPOSE_FILE}' exec -T backend curl -sf http://127.0.0.1:8000/health/ready"

check_step "Next.js Frontend HTTP Response (container:3000/)" \
    "${DOCKER_CMD} compose -f '${COMPOSE_FILE}' exec -T frontend wget -q -O /dev/null --spider http://127.0.0.1:3000/"

check_step "Nginx Reverse Proxy Health Endpoint (http://127.0.0.1/health)" \
    "curl -sf http://127.0.0.1/health -o /dev/null"

check_step "Nginx Frontend Delivery (http://127.0.0.1/)" \
    "curl -sf http://127.0.0.1/ -o /dev/null"

# 6. Worker Safety Verification (Worker must be STOPPED on initial deployment)
echo ""
echo "--- Background Worker Safety Status ---"
WORKER_RUNNING="$(${DOCKER_CMD} compose -f "${COMPOSE_FILE}" ps -q worker 2>/dev/null || true)"
if [[ -z "${WORKER_RUNNING}" ]]; then
    echo "[CHECK] Worker container stopped (Safe initial deployment policy): PASSED"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    echo "[CHECK] WARNING: Worker container is running."
fi

# 7. Database Connectivity & Migration Revision
echo ""
echo "--- Database Status ---"
DB_CONTAINER="$(${DOCKER_CMD} compose -f "${COMPOSE_FILE}" ps -q db 2>/dev/null || true)"
if [[ -n "${DB_CONTAINER}" ]]; then
    DB_USER="${POSTGRES_USER:-metroscope_user}"
    DB_NAME="${POSTGRES_DB:-metroscope}"
    DB_PASS="${POSTGRES_PASSWORD:-}"
    
    ALEMBIC_REV="$(${DOCKER_CMD} exec -e PGPASSWORD="${DB_PASS}" "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" -t -c "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null | tr -d '[:space:]' || echo 'N/A')"
    echo "Current Alembic Migration Revision: ${ALEMBIC_REV}"
    if [[ "${ALEMBIC_REV}" != "N/A" && -n "${ALEMBIC_REV}" ]]; then
        echo "[CHECK] Database Schema at Revision: PASSED (${ALEMBIC_REV})"
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        echo "[CHECK] Database Schema at Revision: FAILED"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
else
    echo "Database container not currently accessible."
fi

# 8. Container Memory Usage against 1,408 MB Budget
echo ""
echo "--- Container Memory Allocations (Budget: 1,408 MB Max) ---"
${DOCKER_CMD} stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}" 2>/dev/null || echo "Docker stats unavailable"

# 9. Disk Space on Host
echo ""
echo "--- Host Disk Space ---"
df -h / | awk 'NR==1 || NR==2'

echo ""
echo "=============================================================================="
echo "Validation Complete: ${PASS_COUNT} checks passed, ${FAIL_COUNT} checks failed."
echo "=============================================================================="

if [[ ${FAIL_COUNT} -eq 0 ]]; then
    exit 0
else
    exit 1
fi
