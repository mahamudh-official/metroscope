#!/usr/bin/env bash
# ==============================================================================
# MetroScope — Local Status Script (Bash)
# Reports health, connectivity, and active configurations across all local services
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

echo -e "\033[1;36m==================================================================\033[0m"
echo -e "\033[1;36m               METROSCOPE — LOCAL SERVICE STATUS                 \033[0m"
echo -e "\033[1;36m==================================================================\033[0m"

# 1. PostgreSQL Check
PG_PORT="${POSTGRES_PORT:-5433}"
if command -v pg_isready >/dev/null 2>&1 && pg_isready -h 127.0.0.1 -p "${PG_PORT}" >/dev/null 2>&1; then
    echo -e "  PostgreSQL Database : \033[1;32mONLINE (Port ${PG_PORT})\033[0m"
else
    echo -e "  PostgreSQL Database : \033[1;31mDOWN (Port ${PG_PORT})\033[0m"
fi

# 2. FastAPI Backend Check
if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo -e "  FastAPI Backend API : \033[1;32mHEALTHY (Port 8000)\033[0m"
    METRICS="$(curl -sf http://127.0.0.1:8000/health/metrics 2>/dev/null || true)"
else
    echo -e "  FastAPI Backend API : \033[1;31mDOWN (Port 8000)\033[0m"
    METRICS=""
fi

# 3. Next.js Frontend Check
if curl -sf http://127.0.0.1:3000/ >/dev/null 2>&1; then
    echo -e "  Next.js Frontend    : \033[1;32mREADY (Port 3000)\033[0m"
else
    echo -e "  Next.js Frontend    : \033[1;31mDOWN (Port 3000)\033[0m"
fi

# 4. Background Worker Check
PID_FILE="${PROJECT_ROOT}/.pids/worker.pid"
if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
    echo -e "  Background Worker   : \033[1;32mRUNNING (PID: $(cat "${PID_FILE}"))\033[0m"
else
    echo -e "  Background Worker   : \033[1;31mSTOPPED\033[0m"
fi

# 5. Display Metrics
echo -e "------------------------------------------------------------------"
if [[ -n "${METRICS}" ]]; then
    echo -e "  * Metrics: ${METRICS}"
else
    echo -e "  * Metrics unavailable (start backend to view live metrics)."
fi
echo -e "\033[1;36m==================================================================\n\033[0m"
