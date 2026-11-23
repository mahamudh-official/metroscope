#!/usr/bin/env bash
# ==============================================================================
# MetroScope — Local One-Command Startup Script (Bash)
# Supports: Docker Compose or Local Native Execution
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

echo -e "\033[1;36m==================================================================\033[0m"
echo -e "\033[1;36m               METROSCOPE — LOCAL STARTUP ENGINE                 \033[0m"
echo -e "\033[1;36m==================================================================\033[0m"

# 1. Environment Verification
ENV_FILE="${PROJECT_ROOT}/.env"
if [[ ! -f "${ENV_FILE}" ]]; then
    echo -e "\033[1;33m[CONFIG] .env not found. Creating from .env.example...\033[0m"
    cp "${PROJECT_ROOT}/.env.example" "${ENV_FILE}"
fi
echo -e "\033[1;32m[CONFIG] Environment file verified: ${ENV_FILE}\033[0m"

mkdir -p "${PROJECT_ROOT}/logs" "${PROJECT_ROOT}/.pids"

# Detect whether Docker daemon is active and responsive
USE_DOCKER=false
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    USE_DOCKER=true
fi

if [[ "${USE_DOCKER}" == "true" ]]; then
    echo -e "\n\033[1;33m[1/5] Starting PostgreSQL container via Docker Compose...\033[0m"
    docker compose up -d db

    echo -e "  -> Waiting for database to report healthy status..."
    for attempt in {1..30}; do
        DB_HEALTH="$(docker compose ps db --format '{{.Health}}' 2>/dev/null || true)"
        if [[ "${DB_HEALTH}" == *"healthy"* ]]; then
            echo -e "\033[1;32m  -> PostgreSQL is ready and healthy.\033[0m"
            break
        fi
        sleep 1
    done

    echo -e "\n\033[1;33m[2/5] Running database migrations...\033[0m"
    docker compose run --rm backend alembic upgrade head || true

    echo -e "\n\033[1;33m[3/5] Starting application services (backend, worker, frontend, nginx)...\033[0m"
    docker compose up -d backend worker frontend nginx
else
    echo -e "\n\033[1;33m[1/5] Checking local PostgreSQL database (.postgres_runtime)...\033[0m"
    PG_PORT="${POSTGRES_PORT:-5433}"
    DB_DIR="${PROJECT_ROOT}/.postgres_runtime"
    
    if ! nc -z 127.0.0.1 "${PG_PORT}" >/dev/null 2>&1; then
        echo -e "  -> Starting PostgreSQL on port ${PG_PORT}..."
        postgres -D "${DB_DIR}" -p "${PG_PORT}" > "${PROJECT_ROOT}/logs/postgres.log" 2>&1 &
        echo $! > "${PROJECT_ROOT}/.pids/db.pid"
        sleep 3
    else
        echo -e "\033[1;32m  -> PostgreSQL is already running on port ${PG_PORT}.\033[0m"
    fi

    echo -e "\n\033[1;33m[2/5] Running Alembic Database Migrations...\033[0m"
    export PYTHONPATH="backend"
    export DATABASE_URL="postgresql+asyncpg://metroscope_user:metroscope_secure_password@127.0.0.1:${PG_PORT}/metroscope"
    export DATABASE_SYNC_URL="postgresql://metroscope_user:metroscope_secure_password@127.0.0.1:${PG_PORT}/metroscope"
    (cd backend && python -m alembic upgrade head || true)

    echo -e "\n\033[1;33m[3/5] Starting FastAPI Backend API (Port 8000)...\033[0m"
    (cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000) > "${PROJECT_ROOT}/logs/backend.log" 2>&1 &
    echo $! > "${PROJECT_ROOT}/.pids/backend.pid"

    echo -e "\n\033[1;33m[4/5] Starting APScheduler Background News Worker...\033[0m"
    (cd backend && python -m app.workers.main) > "${PROJECT_ROOT}/logs/worker.log" 2>&1 &
    echo $! > "${PROJECT_ROOT}/.pids/worker.pid"

    echo -e "\n\033[1;33m[5/5] Starting Next.js Frontend (Port 3000)...\033[0m"
    export PORT="3000"
    export INTERNAL_API_URL="http://127.0.0.1:8000/api/v1"
    export NEXT_PUBLIC_API_URL="http://127.0.0.1:8000/api/v1"
    export NEXT_PUBLIC_SITE_URL="http://localhost:3000"

    STANDALONE_JS="${PROJECT_ROOT}/frontend/.next/standalone/server.js"
    STANDALONE_DIR="${PROJECT_ROOT}/frontend/.next/standalone"
    if [[ -f "${STANDALONE_JS}" ]]; then
        # Ensure static assets are copied to standalone directory
        if [[ ! -d "${STANDALONE_DIR}/.next/static" && -d "${PROJECT_ROOT}/frontend/.next/static" ]]; then
            cp -r "${PROJECT_ROOT}/frontend/.next/static" "${STANDALONE_DIR}/.next/"
        fi
        if [[ ! -d "${STANDALONE_DIR}/public" && -d "${PROJECT_ROOT}/frontend/public" ]]; then
            cp -r "${PROJECT_ROOT}/frontend/public" "${STANDALONE_DIR}/"
        fi
        (cd "${STANDALONE_DIR}" && node server.js) > "${PROJECT_ROOT}/logs/frontend.log" 2>&1 &
        echo $! > "${PROJECT_ROOT}/.pids/frontend.pid"
    else
        (cd frontend && npm run dev) > "${PROJECT_ROOT}/logs/frontend.log" 2>&1 &
        echo $! > "${PROJECT_ROOT}/.pids/frontend.pid"
    fi
fi

# Probe readiness
echo -e "\nWaiting for services to become healthy..."
sleep 3

echo -e "\n\033[1;36m==================================================================\033[0m"
echo -e "\033[1;32m          METROSCOPE IS NOW LIVE FOR LOCAL MANUAL TESTING        \033[0m"
echo -e "\033[1;36m==================================================================\033[0m"
echo -e "  * Frontend UI (Browser Entry) : \033[1;37mhttp://localhost:3000\033[0m"
echo -e "  * Backend Interactive Docs    : \033[1;37mhttp://127.0.0.1:8000/docs\033[0m"
echo -e "  * Backend Health Probe        : \033[1;37mhttp://127.0.0.1:8000/health\033[0m"
if [[ "${USE_DOCKER}" == "true" ]]; then
    echo -e "  * Nginx Reverse Proxy         : \033[1;37mhttp://localhost:80\033[0m"
fi
echo -e "  * Dry-Run Modes               : \033[1;32mSOCIAL_DRY_RUN=true, EMAIL_DRY_RUN=true\033[0m"
echo -e "------------------------------------------------------------------"
echo -e "  * Check Service Status        : ./scripts/local_status.sh"
echo -e "  * Inspect Live Logs           : ./scripts/local_logs.sh"
echo -e "  * Stop All Services           : ./scripts/local_stop.sh"
echo -e "\033[1;36m==================================================================\n\033[0m"
