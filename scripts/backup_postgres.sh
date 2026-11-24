#!/usr/bin/env bash
# ==============================================================================
# MetroScope — Automated PostgreSQL Backup Script with Tiered Retention
# Target: AWS EC2 t3.small, Ubuntu 24.04 LTS, Docker Compose
# Retention Policy: 7 Daily, 4 Weekly, 3 Monthly Backups
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

# Default to /srv/metroscope/backups if it exists on host, else local backups dir
if [[ -d "/srv/metroscope/backups" ]]; then
    BACKUP_ROOT="/srv/metroscope/backups"
else
    BACKUP_ROOT="${PROJECT_ROOT}/backups"
fi
BACKUP_DIR="${BACKUP_DIR:-${BACKUP_ROOT}}"

DAILY_DIR="${BACKUP_DIR}/daily"
WEEKLY_DIR="${BACKUP_DIR}/weekly"
MONTHLY_DIR="${BACKUP_DIR}/monthly"

mkdir -p "${DAILY_DIR}" "${WEEKLY_DIR}" "${MONTHLY_DIR}"

LOG_FILE="${BACKUP_DIR}/backup.log"
TIMESTAMP="$(date -u +"%Y%m%d_%H%M%SZ")"
DATE_ONLY="$(date -u +"%Y%m%d")"
DAY_OF_WEEK="$(date -u +"%u")"  # 1 = Monday, 7 = Sunday
DAY_OF_MONTH="$(date -u +"%d")" # 01-31

BACKUP_BASENAME="metroscope_pg_${TIMESTAMP}.sql.gz"
DAILY_FILE="${DAILY_DIR}/${BACKUP_BASENAME}"
DAILY_CHECKSUM="${DAILY_FILE}.sha256"

# Retention Policies
RETENTION_DAILY_DAYS=7
RETENTION_WEEKLY_DAYS=28
RETENTION_MONTHLY_DAYS=90

# Optional Remote Storage
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:-}"

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
    echo "[${ts}] [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log "INFO" "=================================================================="
log "INFO" "Starting MetroScope PostgreSQL logical backup..."
log "INFO" "Backup Target: ${DAILY_FILE}"
log "INFO" "=================================================================="

# Determine Compose file
COMPOSE_FILE="${COMPOSE_FILE:-${PROJECT_ROOT}/docker-compose.prod.yml}"
if [[ ! -f "${COMPOSE_FILE}" ]]; then
    COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
fi

# Locate running database container
CONTAINER_NAME="${CONTAINER_NAME:-$(${DOCKER_CMD} compose -f "${COMPOSE_FILE}" ps -q db 2>/dev/null || true)}"
if [[ -z "${CONTAINER_NAME}" ]]; then
    log "ERROR" "PostgreSQL container (service 'db') is not running. Aborting backup."
    exit 1
fi

# Load database credentials from .env
ENV_FILE="${PROJECT_ROOT}/.env"
if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

DB_USER="${POSTGRES_USER:-metroscope_user}"
DB_NAME="${POSTGRES_DB:-metroscope}"
DB_PASS="${POSTGRES_PASSWORD:-}"

if [[ -z "${DB_PASS}" ]]; then
    log "ERROR" "POSTGRES_PASSWORD is not set. Aborting backup."
    exit 1
fi

log "INFO" "Executing pg_dump for database '${DB_NAME}' via container '${CONTAINER_NAME}'..."

# Execute pg_dump, compress with gzip -9, write to daily directory
if ${DOCKER_CMD} exec -i -e PGPASSWORD="${DB_PASS}" "${CONTAINER_NAME}" \
    pg_dump -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists --no-owner --no-privileges \
    | gzip -9 > "${DAILY_FILE}"; then

    # 1. Verify Gzip Integrity
    if gzip -t "${DAILY_FILE}"; then
        BACKUP_SIZE="$(du -h "${DAILY_FILE}" | cut -f1)"
        log "INFO" "Backup created and integrity verified: ${DAILY_FILE} (${BACKUP_SIZE})"
        
        # 2. Compute SHA-256 Checksum
        if command -v sha256sum >/dev/null 2>&1; then
            sha256sum "${DAILY_FILE}" > "${DAILY_CHECKSUM}"
        elif command -v shasum >/dev/null 2>&1; then
            shasum -a 256 "${DAILY_FILE}" > "${DAILY_CHECKSUM}"
        fi
        log "INFO" "Integrity checksum generated: ${DAILY_CHECKSUM}"
    else
        log "ERROR" "Gzip integrity verification failed for ${DAILY_FILE}. Removing corrupted file."
        rm -f "${DAILY_FILE}"
        exit 1
    fi
else
    log "ERROR" "pg_dump failed during execution."
    rm -f "${DAILY_FILE}"
    exit 1
fi

# 3. Tiered Promotion: Weekly (every Sunday, DAY_OF_WEEK=7)
if [[ "${DAY_OF_WEEK}" -eq 7 ]]; then
    log "INFO" "Today is Sunday. Promoting backup to Weekly tier (${WEEKLY_DIR})..."
    cp -f "${DAILY_FILE}" "${WEEKLY_DIR}/${BACKUP_BASENAME}"
    cp -f "${DAILY_CHECKSUM}" "${WEEKLY_DIR}/${BACKUP_BASENAME}.sha256"
fi

# 4. Tiered Promotion: Monthly (1st of month, DAY_OF_MONTH=01)
if [[ "${DAY_OF_MONTH}" == "01" ]]; then
    log "INFO" "Today is the 1st of the month. Promoting backup to Monthly tier (${MONTHLY_DIR})..."
    cp -f "${DAILY_FILE}" "${MONTHLY_DIR}/${BACKUP_BASENAME}"
    cp -f "${DAILY_CHECKSUM}" "${MONTHLY_DIR}/${BACKUP_BASENAME}.sha256"
fi

# 5. Enforce Retention Policy
log "INFO" "Enforcing retention policy:"
log "INFO" "- Daily: pruning archives older than ${RETENTION_DAILY_DAYS} days..."
find "${DAILY_DIR}" -name "metroscope_pg_*.sql.gz*" -type f -mtime +"${RETENTION_DAILY_DAYS}" -exec rm -f {} +

log "INFO" "- Weekly: pruning archives older than ${RETENTION_WEEKLY_DAYS} days..."
find "${WEEKLY_DIR}" -name "metroscope_pg_*.sql.gz*" -type f -mtime +"${RETENTION_WEEKLY_DAYS}" -exec rm -f {} +

log "INFO" "- Monthly: pruning archives older than ${RETENTION_MONTHLY_DAYS} days..."
find "${MONTHLY_DIR}" -name "metroscope_pg_*.sql.gz*" -type f -mtime +"${RETENTION_MONTHLY_DAYS}" -exec rm -f {} +

# 6. Optional Remote S3 Sync
if [[ -n "${BACKUP_S3_BUCKET}" ]]; then
    if command -v aws >/dev/null 2>&1; then
        log "INFO" "Uploading daily backup to AWS S3: s3://${BACKUP_S3_BUCKET}/backups/daily/"
        if aws s3 cp "${DAILY_FILE}" "s3://${BACKUP_S3_BUCKET}/backups/daily/${BACKUP_BASENAME}" && \
           aws s3 cp "${DAILY_CHECKSUM}" "s3://${BACKUP_S3_BUCKET}/backups/daily/${BACKUP_BASENAME}.sha256"; then
            log "INFO" "Successfully synced backup to S3."
        else
            log "WARNING" "S3 backup upload encountered an error. Local backup remains preserved."
        fi
    else
        log "WARNING" "BACKUP_S3_BUCKET specified but 'aws' CLI is not installed. Skipping remote sync."
    fi
fi

# 7. Write Portability Manifest
MANIFEST_FILE="${BACKUP_DIR}/latest_backup_manifest.json"
cat > "${MANIFEST_FILE}" <<EOF
{
  "timestamp": "${TIMESTAMP}",
  "date": "${DATE_ONLY}",
  "backup_file": "${DAILY_FILE}",
  "backup_basename": "${BACKUP_BASENAME}",
  "size": "${BACKUP_SIZE}",
  "sha256": "$(cat "${DAILY_CHECKSUM}" | awk '{print $1}')",
  "database": "${DB_NAME}",
  "postgres_version": "16-alpine",
  "retention_tier": "7_daily_4_weekly_3_monthly",
  "portable_target": "AWS_EC2_OR_HOSTINGER_VPS"
}
EOF

log "INFO" "Portability manifest written to ${MANIFEST_FILE}"
log "INFO" "=================================================================="
log "INFO" "MetroScope PostgreSQL backup process completed successfully."
log "INFO" "=================================================================="
exit 0
