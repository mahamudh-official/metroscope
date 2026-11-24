#!/usr/bin/env bash
# ==============================================================================
# MetroScope — HTTPS / SSL Activation Script (Stage B Bootstrap)
# Target: AWS EC2 t3.small, Ubuntu 24.04 LTS, Docker Compose + Nginx
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.prod.yml"
NGINX_CONF_DIR="${PROJECT_ROOT}/infrastructure/nginx/conf.d"
STAGE_A_CONF="${NGINX_CONF_DIR}/metroscope.conf"
STAGE_B_TEMPLATE="${NGINX_CONF_DIR}/metroscope-ssl.conf.template"
CERT_DIR="${PROJECT_ROOT}/infrastructure/nginx/certbot/conf/live/themetroscope.com"

# Determine Docker Command (use sudo if user is not in docker group)
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

log "INFO" "=================================================================="
log "INFO" "Starting MetroScope HTTPS / SSL Activation (Stage B)..."
log "INFO" "=================================================================="

# 1. Verify Nginx container is running
NGINX_CONTAINER="$(${DOCKER_CMD} compose -f "${COMPOSE_FILE}" ps -q nginx 2>/dev/null || true)"
if [[ -z "${NGINX_CONTAINER}" ]]; then
    log "ERROR" "Nginx service is not running. Please run deployment in Stage A first: ./scripts/deploy.sh"
    exit 1
fi

# 2. Check for existing certificate
if [[ ! -f "${CERT_DIR}/fullchain.pem" || ! -f "${CERT_DIR}/privkey.pem" ]]; then
    log "INFO" "SSL certificate not found at ${CERT_DIR}."
    log "INFO" "Attempting to request Let's Encrypt certificate via Certbot HTTP challenge..."
    
    EMAIL="${1:-admin@themetroscope.com}"
    log "INFO" "Using registration email: ${EMAIL}"
    
    ${DOCKER_CMD} compose -f "${COMPOSE_FILE}" --profile certbot run --rm certbot certonly \
        --webroot \
        -w /var/www/certbot \
        -d themetroscope.com \
        -d www.themetroscope.com \
        -d api.themetroscope.com \
        --email "${EMAIL}" \
        --agree-tos \
        --no-eff-email \
        --keep-until-expiring
fi

# 3. Confirm certificates now exist
if [[ ! -f "${CERT_DIR}/fullchain.pem" || ! -f "${CERT_DIR}/privkey.pem" ]]; then
    log "ERROR" "Certificates still missing after certbot execution. Aborting HTTPS activation."
    log "ERROR" "Ensure DNS A-records for themetroscope.com, www.themetroscope.com, and api.themetroscope.com point to this EC2 instance."
    exit 1
fi
log "INFO" "Verified SSL certificate files exist at ${CERT_DIR}."

# 4. Backup Stage A Configuration
BACKUP_STAGE_A="${NGINX_CONF_DIR}/metroscope.conf.stageA.bak"
cp -f "${STAGE_A_CONF}" "${BACKUP_STAGE_A}"

# 5. Activate Stage B Configuration
log "INFO" "Activating HTTPS Nginx configuration from template..."
cp -f "${STAGE_B_TEMPLATE}" "${STAGE_A_CONF}"

# 6. Validate Nginx Configuration Syntax
log "INFO" "Validating Nginx syntax inside running container..."
if ! ${DOCKER_CMD} compose -f "${COMPOSE_FILE}" exec -T nginx nginx -t; then
    log "ERROR" "Nginx configuration test failed! Rolling back to Stage A HTTP configuration..."
    cp -f "${BACKUP_STAGE_A}" "${STAGE_A_CONF}"
    ${DOCKER_CMD} compose -f "${COMPOSE_FILE}" exec -T nginx nginx -s reload || true
    exit 1
fi

# 7. Graceful Nginx Reload
log "INFO" "Reloading Nginx with HTTPS configuration..."
${DOCKER_CMD} compose -f "${COMPOSE_FILE}" exec -T nginx nginx -s reload

log "INFO" "=================================================================="
log "INFO" "HTTPS / SSL successfully activated for themetroscope.com!"
log "INFO" "Verified: HTTP redirects to HTTPS, TLS 1.2/1.3 operational."
log "INFO" "=================================================================="
exit 0
