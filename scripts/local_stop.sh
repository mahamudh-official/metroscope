#!/usr/bin/env bash
# ==============================================================================
# MetroScope — Local Stop Script (Bash)
# Safely stops all containers and background processes without deleting volumes
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

echo -e "\033[1;36m==================================================================\033[0m"
echo -e "\033[1;36m               STOPPING METROSCOPE LOCAL SERVICES                \033[0m"
echo -e "\033[1;36m==================================================================\033[0m"

# Stop background processes by PID
PID_DIR="${PROJECT_ROOT}/.pids"
if [[ -d "${PID_DIR}" ]]; then
    for pid_file in "${PID_DIR}"/*.pid; do
        if [[ -f "${pid_file}" ]]; then
            service_name="$(basename "${pid_file}" .pid)"
            pid="$(cat "${pid_file}")"
            if kill -0 "${pid}" 2>/dev/null; then
                echo -e "Stopping ${service_name} (PID: ${pid})..."
                kill "${pid}" 2>/dev/null || true
            fi
            rm -f "${pid_file}"
        fi
    done
fi

# Stop PostgreSQL cleanly via pg_ctl if present
if command -v pg_ctl >/dev/null 2>&1; then
    pg_ctl -D "${PROJECT_ROOT}/.postgres_runtime" stop -m fast >/dev/null 2>&1 || true
fi

# Stop Docker Compose services if running
if command -v docker >/dev/null 2>&1 && docker compose ps -q 2>/dev/null | grep -q .; then
    echo -e "Stopping Docker Compose containers..."
    docker compose stop
fi

echo -e "\n\033[1;32mAll MetroScope services stopped safely.\033[0m"
echo -e "\033[1;36mDatabase records are preserved intact.\033[0m\n"
