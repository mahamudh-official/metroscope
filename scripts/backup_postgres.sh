#!/usr/bin/env bash
# ==============================================================================
# MetroScope — Automated PostgreSQL Backup Script
# Platform: AWS EC2 t3.small, Ubuntu 24.04 LTS, Docker Compose
# ==============================================================================
set -Eeuo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${PROJECT_ROOT}/backups}"
TIMESTAMP="$(date -u +"%Y%m%d_%H%M%SZ")"
DATE_ONLY="$(date -u +"%Y%m%d")"
BACKUP_FILE="${BACKUP_DIR}/metroscope_pg_${TIMESTAMP}.sql.gz"
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
LOG_FILE="${BACKUP_DIR}/backup.log"

# Retention Policies (Configurable via environment)
RETENTION_DAILY_DAYS="${RETENTION_DAILY_DAYS:-7}"
RETENTION_WEEKLY_DAYS="${RETENTION_WEEKLY_DAYS:-28}"
RETENTION_MONTHLY_DAYS="${RETENTION_MONTHLY_DAYS:-90}"

# Optional Remote Storage
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:-}"

# Create backup directory if it does not exist
mkdir -p "${BACKUP_DIR}"

log() {
    local level="$1"
    local message="$2"
    local ts
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "[${ts}] [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log "INFO" "Starting MetroScope PostgreSQL backup..."

# Determine Docker Compose file and project name
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
if [[ ! -f "${COMPOSE_FILE}" ]]; then
    COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
fi

# Determine DB container name
CONTAINER_NAME="$(docker compose -f "${COMPOSE_FILE}" ps -q db 2>/dev/null || true)"
if [[ -z "${CONTAINER_NAME}" ]]; then
    log "ERROR" "PostgreSQL container (service 'db') is not running. Aborting backup."
    exit 1
fi

# Load database credentials from environment or .env file
ENV_FILE="${PROJECT_ROOT}/.env"
if [[ -f "${ENV_FILE}" ]]; then
    # shellcheck disable=SC1090
    set -a
    source "${ENV_FILE}"
    set +a
fi

DB_USER="${POSTGRES_USER:-metroscope_user}"
DB_NAME="${POSTGRES_DB:-metroscope}"

log "INFO" "Executing pg_dump for database '${DB_NAME}' via container '${CONTAINER_NAME}'..."

# Execute pg_dump, compress with gzip, write directly to destination
if docker exec -e PGPASSWORD="${POSTGRES_PASSWORD}" "${CONTAINER_NAME}" \
    pg_dump -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists --no-owner --no-privileges \
    | gzip -9 > "${BACKUP_FILE}"; then
    
    # Verify backup integrity
    if gzip -t "${BACKUP_FILE}"; then
        BACKUP_SIZE="$(du -h "${BACKUP_FILE}" | cut -f1)"
        log "INFO" "Backup successfully created and verified: ${BACKUP_FILE} (${BACKUP_SIZE})"
        
        # Compute SHA-256 Checksum
        if command -v sha256sum >/dev/null 2>&1; then
            sha256sum "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
        elif command -v shasum >/dev/null 2>&1; then
            shasum -a 256 "${BACKUP_FILE}" > "${CHECKSUM_FILE}"
        fi
        log "INFO" "Integrity checksum generated: ${CHECKSUM_FILE}"
    else
        log "ERROR" "Gzip integrity verification failed for ${BACKUP_FILE}. Removing corrupted file."
        rm -f "${BACKUP_FILE}"
        exit 1
    fi
else
    log "ERROR" "pg_dump failed during execution."
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# Optional Remote S3 Sync
if [[ -n "${BACKUP_S3_BUCKET}" ]]; then
    if command -v aws >/dev/null 2>&1; then
        log "INFO" "Uploading backup to AWS S3: s3://${BACKUP_S3_BUCKET}/backups/"
        if aws s3 cp "${BACKUP_FILE}" "s3://${BACKUP_S3_BUCKET}/backups/$(basename "${BACKUP_FILE}")" && \
           aws s3 cp "${CHECKSUM_FILE}" "s3://${BACKUP_S3_BUCKET}/backups/$(basename "${CHECKSUM_FILE}")"; then
            log "INFO" "Successfully synced backup to S3."
        else
            log "WARNING" "S3 backup upload encountered an error. Local backup remains preserved."
        fi
    else
        log "WARNING" "BACKUP_S3_BUCKET specified but 'aws' CLI is not installed. Skipping remote sync."
    fi
fi

# Enforce Retention Policy
log "INFO" "Pruning local backups older than ${RETENTION_DAILY_DAYS} days..."
find "${BACKUP_DIR}" -name "metroscope_pg_*.sql.gz" -type f -mtime +"${RETENTION_DAILY_DAYS}" -exec rm -f {} +
find "${BACKUP_DIR}" -name "metroscope_pg_*.sql.gz.sha256" -type f -mtime +"${RETENTION_DAILY_DAYS}" -exec rm -f {} +

log "INFO" "PostgreSQL backup process completed successfully."
exit 0
