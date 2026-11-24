#!/usr/bin/env bash
# ==============================================================================
# MetroScope — PostgreSQL Database Restore Script
# Target: AWS EC2 t3.small, Ubuntu 24.04 LTS, Docker Compose
# Deployment Path: /srv/metroscope/app
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

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
    echo "[${ts}] [${level}] ${message}"
}

usage() {
    echo "Usage: $0 <path_to_backup_file.sql.gz> [--force]"
    echo ""
    echo "Examples:"
    echo "  $0 /srv/metroscope/backups/daily/metroscope_pg_20261124_120000Z.sql.gz"
    echo "  $0 backups/daily/metroscope_pg_20261124_120000Z.sql.gz --force"
    echo ""
    echo "Options:"
    echo "  --force    Bypass interactive confirmation (use with caution in scripts)"
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi

BACKUP_FILE="$1"
FORCE_RESTORE=false

if [[ $# -ge 2 && "$2" == "--force" ]]; then
    FORCE_RESTORE=true
fi

if [[ ! -f "${BACKUP_FILE}" ]]; then
    log "ERROR" "Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

log "INFO" "Verifying backup file integrity for: ${BACKUP_FILE}"

# 1. Verify Gzip Integrity
if ! gzip -t "${BACKUP_FILE}"; then
    log "ERROR" "Gzip archive corrupted or incomplete. Aborting restore."
    exit 1
fi

# 2. Verify SHA-256 Checksum if present
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
if [[ -f "${CHECKSUM_FILE}" ]]; then
    log "INFO" "Verifying SHA-256 checksum against ${CHECKSUM_FILE}..."
    if command -v sha256sum >/dev/null 2>&1; then
        (cd "$(dirname "${BACKUP_FILE}")" && sha256sum -c "$(basename "${CHECKSUM_FILE}")") || {
            log "ERROR" "SHA-256 checksum verification failed! Aborting restore."
            exit 1
        }
    elif command -v shasum >/dev/null 2>&1; then
        (cd "$(dirname "${BACKUP_FILE}")" && shasum -a 256 -c "$(basename "${CHECKSUM_FILE}")") || {
            log "ERROR" "SHA-256 checksum verification failed! Aborting restore."
            exit 1
        }
    fi
    log "INFO" "Checksum verification passed."
fi

# 3. Locate PostgreSQL Container
COMPOSE_FILE="${COMPOSE_FILE:-${PROJECT_ROOT}/docker-compose.prod.yml}"
if [[ ! -f "${COMPOSE_FILE}" ]]; then
    COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
fi

CONTAINER_NAME="${CONTAINER_NAME:-$(${DOCKER_CMD} compose -f "${COMPOSE_FILE}" ps -q db 2>/dev/null || true)}"
if [[ -z "${CONTAINER_NAME}" ]]; then
    log "ERROR" "PostgreSQL container (service 'db') is not running. Start services before restoring."
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

# 4. Interactive Confirmation
if [[ "${FORCE_RESTORE}" != "true" ]]; then
    echo "=============================================================================="
    echo "WARNING: Restoring will overwrite existing data in database '${DB_NAME}'."
    echo "Backup target: ${BACKUP_FILE}"
    echo "Container:     ${CONTAINER_NAME}"
    echo "=============================================================================="
    read -r -p "Are you sure you want to proceed with database restore? (yes/NO): " confirm
    if [[ "${confirm}" != "yes" ]]; then
        log "INFO" "Restore cancelled by user."
        exit 0
    fi
fi

log "INFO" "Executing database restoration..."

# Decompress and stream directly into psql
if gzip -dc "${BACKUP_FILE}" | ${DOCKER_CMD} exec -i -e PGPASSWORD="${DB_PASS}" "${CONTAINER_NAME}" \
    psql -U "${DB_USER}" -d "${DB_NAME}" -v ON_ERROR_STOP=1 > /dev/null; then
    
    log "INFO" "Database restore executed successfully."
else
    log "ERROR" "Database restore encountered an error during psql execution."
    exit 1
fi

# 5. Post-Restore Integrity Verification
log "INFO" "Running post-restore database verification queries..."

VERIFY_QUERY="
SELECT 'news_articles' AS entity, count(*) FROM news_articles
UNION ALL
SELECT 'news_sources' AS entity, count(*) FROM news_sources
UNION ALL
SELECT 'news_categories' AS entity, count(*) FROM news_categories
UNION ALL
SELECT 'social_posts' AS entity, count(*) FROM social_posts
UNION ALL
SELECT 'email_subscribers' AS entity, count(*) FROM email_subscribers
UNION ALL
SELECT 'newsletter_campaigns' AS entity, count(*) FROM newsletter_campaigns
UNION ALL
SELECT 'alembic_version' AS entity, count(*) FROM alembic_version;
"

echo "--- Post-Restore Entity Counts ---"
${DOCKER_CMD} exec -e PGPASSWORD="${DB_PASS}" "${CONTAINER_NAME}" \
    psql -U "${DB_USER}" -d "${DB_NAME}" -c "${VERIFY_QUERY}"

ALEMBIC_REV="$(${DOCKER_CMD} exec -e PGPASSWORD="${DB_PASS}" "${CONTAINER_NAME}" \
    psql -U "${DB_USER}" -d "${DB_NAME}" -t -c "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"

log "INFO" "Current Alembic database revision at: ${ALEMBIC_REV}"
log "INFO" "Restore procedure completed and verified."
exit 0
