#!/usr/bin/env bash
# ==============================================================================
# MetroScope — Production Deployment Validation Diagnostic Script
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
if [[ ! -f "${COMPOSE_FILE}" ]]; then
    COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
fi

echo "=============================================================================="
echo "          METROSCOPE PRODUCTION DEPLOYMENT VALIDATION REPORT                  "
echo "=============================================================================="
echo "Timestamp:   $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "Host:        $(hostname)"
echo "Compose:     ${COMPOSE_FILE}"
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
check_step "Docker daemon operational" "docker info"
check_step "Docker Compose v2 available" "docker compose version"

# 2. Environment Configuration
check_step "Environment file (.env) exists" "[[ -f '${PROJECT_ROOT}/.env' ]]"
check_step "Docker Compose config valid" "docker compose -f '${COMPOSE_FILE}' config -q"

# 3. Persistent Volumes
check_step "Postgres data volume exists" "docker volume ls | grep -E 'postgres_data|metroscope.*postgres'"

# 4. Container Runtime Health
echo ""
echo "--- Container Status & Health ---"
docker compose -f "${COMPOSE_FILE}" ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}\t{{.Ports}}" || true

echo ""
echo "--- Application Probes ---"
# 5. Local Service Endpoints
check_step "FastAPI Liveness Probe (http://127.0.0.1:8000/health/live)" \
    "curl -sf http://127.0.0.1:8000/health/live"

check_step "FastAPI Readiness Probe (http://127.0.0.1:8000/health/ready)" \
    "curl -sf http://127.0.0.1:8000/health/ready"

check_step "Next.js Frontend HTTP Response (http://127.0.0.1:3000/)" \
    "curl -sf http://127.0.0.1:3000/ -o /dev/null"

check_step "Nginx Reverse Proxy Health (http://127.0.0.1/health)" \
    "curl -sf http://127.0.0.1/health -o /dev/null"

# 6. Database Connectivity & Migration Revision
echo ""
echo "--- Database Status ---"
DB_CONTAINER="$(docker compose -f "${COMPOSE_FILE}" ps -q db 2>/dev/null || true)"
if [[ -n "${DB_CONTAINER}" ]]; then
    ALEMBIC_REV="$(docker exec "${DB_CONTAINER}" psql -U metroscope_user -d metroscope -t -c "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null | tr -d '[:space:]' || echo 'N/A')"
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

# 7. Container Memory Usage against 1,408 MB Budget
echo ""
echo "--- Container Memory Allocations (Budget: 1,408 MB Max) ---"
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}" 2>/dev/null || echo "Docker stats unavailable"

# 8. Disk Space on Host
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
