#!/usr/bin/env bash
# ==============================================================================
# MetroScope — Local Log Inspection Script (Bash)
# Usage: ./scripts/local_logs.sh [backend|worker|frontend|postgres|all] [lines]
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"

SERVICE="${1:-all}"
LINES="${2:-30}"

if [[ ! -d "${LOG_DIR}" ]]; then
    echo "No logs found in ${LOG_DIR}. Start the application first."
    exit 0
fi

show_log() {
    local file="$1"
    local title="$2"
    if [[ -f "${file}" ]]; then
        echo -e "\n\033[1;36m=== [LOG: ${title}] (${file}) ===\033[0m"
        tail -n "${LINES}" "${file}"
    fi
}

if [[ "${SERVICE}" == "backend" || "${SERVICE}" == "all" ]]; then
    show_log "${LOG_DIR}/backend.log" "FastAPI Backend"
fi
if [[ "${SERVICE}" == "worker" || "${SERVICE}" == "all" ]]; then
    show_log "${LOG_DIR}/worker.log" "APScheduler Worker"
fi
if [[ "${SERVICE}" == "frontend" || "${SERVICE}" == "all" ]]; then
    show_log "${LOG_DIR}/frontend.log" "Next.js Frontend"
fi
if [[ "${SERVICE}" == "postgres" || "${SERVICE}" == "all" ]]; then
    show_log "${LOG_DIR}/postgres.log" "PostgreSQL Database"
fi
