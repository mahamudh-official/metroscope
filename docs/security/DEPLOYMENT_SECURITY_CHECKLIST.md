# MetroScope — Production Deployment Security Checklist

**Target Platform:** MetroScope News Aggregation & Publication System  
**Deployment Target:** AWS EC2 (Ubuntu 22.04/24.04 LTS) + Docker Compose  
**Production Domain:** `themetroscope.com` / `api.themetroscope.com`  
**Purpose:** Pre-flight and post-deployment hardening verification for system administrators and DevOps engineers.  
**Auditor Verification Status:** All Pre-Flight Codebase & Configuration Items Verified [x]  

---

## 1. AWS Infrastructure & Host Security (EC2)

*(To be confirmed on the live AWS EC2 host during instance provisioning)*

- [ ] **AWS Security Group Configuration:**
  - [ ] Inbound rule for HTTP (TCP port 80) allowed from `0.0.0.0/0`.
  - [ ] Inbound rule for HTTPS (TCP port 443) allowed from `0.0.0.0/0`.
  - [ ] Inbound rule for SSH (TCP port 22) restricted strictly to administrator/operator static IP addresses (never open to `0.0.0.0/0`).
  - [ ] **ZERO** inbound rules for PostgreSQL (port 5432) or internal container ports (3000, 8000).
- [ ] **AWS Instance Metadata Service v2 (IMDSv2) Enforcement:**
  - [ ] Enforce IMDSv2 tokens only: `aws ec2 modify-instance-metadata-options --instance-id <ID> --http-tokens required --http-endpoint enabled`.
  - [ ] Set HTTP hop limit to 1: `--http-put-response-hop-limit 1` (prevents containers from reaching the host metadata service).
- [ ] **OS-Level SSH & Access Hardening:**
  - [ ] Password authentication disabled in `/etc/ssh/sshd_config` (`PasswordAuthentication no`).
  - [ ] Root login disabled (`PermitRootLogin no`).
  - [ ] SSH key authentication enforced (Ed25519 or RSA 4096).
- [ ] **Host Firewall (UFW) Configuration:**
  - [ ] `ufw default deny incoming`
  - [ ] `ufw default allow outgoing`
  - [ ] `ufw allow 22/tcp` (restricted to admin IP if not done in Security Group)
  - [ ] `ufw allow 80/tcp`
  - [ ] `ufw allow 443/tcp`
  - [ ] Verify Docker does not bypass UFW by installing `ufw-docker` or setting `DOCKER_OPTS="--iptables=false"` if required.
- [ ] **System Updates & Intrusion Prevention:**
  - [ ] Automatic security updates enabled (`apt-get install unattended-upgrades`).
  - [ ] Fail2ban installed and configured for SSH protection (`apt-get install fail2ban`).

---

## 2. Docker & Container Isolation

- [x] **Docker Compose Production Mode (Verified in Codebase):**
  - [x] Exclusively execute `docker compose -f docker-compose.prod.yml up -d` in production.
  - [x] Never run development `docker-compose.yml` on production hosts.
- [x] **Network & Port Isolation (Verified in Codebase):**
  - [x] Confirmed `docker-compose.prod.yml` has **NO** `ports` directive for the `db` service.
  - [x] Confirmed `docker-compose.yml` binds `db` strictly to `127.0.0.1` (`127.0.0.1:${POSTGRES_PORT:-5432}:5432`).
  - [x] Confirmed containers communicate exclusively over the private bridge network (`metroscope_net`).
- [x] **Container Privilege Hardening (Verified in Codebase):**
  - [x] Security flags verified across compose files.
  - [x] Application containers configured for unprivileged execution (`nextjs:nodejs` user).
  - [x] Frontend standalone image includes native `sharp 0.35.5` + `libvips 8.18.7` (GHSA-2464-fhr4-w9xw runtime mitigation verified).
  - [x] Production container runs Node.js `v20.20.2` (>= 20.9.0 requirement satisfied).
  - [x] DevDependencies (`eslint`, `@typescript-eslint`, `rimraf`, `glob`) excluded from runner stage.
- [ ] **Resource Limits (CPU / Memory):**
  - [ ] Set resource constraints in `docker-compose.prod.yml` prior to launch:
    ```yaml
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 2048M
    ```

---

## 3. Reverse Proxy & TLS Configuration (Nginx)

- [x] **Domain & Host Configuration (Verified in Codebase):**
  - [x] Updated `server_name` in `infrastructure/nginx/conf.d/metroscope.conf` from `metroscope.news` to `themetroscope.com www.themetroscope.com api.themetroscope.com`.
  - [ ] Obtain and install Let's Encrypt certificates for `themetroscope.com` and `api.themetroscope.com` upon DNS propagation.
- [x] **Enforce HTTPS & Redirection (Verified in Codebase):**
  - [x] Port 80 configured to unconditionally issue a `301 Moved Permanently` redirect to `https://$host$request_uri`.
- [x] **HTTP Strict Transport Security (HSTS) (Verified in Codebase):**
  - [x] Enabled HSTS header: `add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;`.
- [x] **Modern SSL/TLS Protocols & Ciphers (Verified in Codebase):**
  - [x] Enabled TLSv1.2 and TLSv1.3 only: `ssl_protocols TLSv1.2 TLSv1.3;`.
  - [x] High-security cipher suites configured.
  - [x] OCSP Stapling directives configured.
- [x] **Security Response Headers (Verified in Codebase):**
  - [x] `add_header X-Content-Type-Options "nosniff" always;`
  - [x] `add_header X-Frame-Options "SAMEORIGIN" always;`
  - [x] `add_header Referrer-Policy "strict-origin-when-cross-origin" always;`
  - [x] `add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;`
  - [x] `add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; font-src 'self' data:; connect-src 'self' https://themetroscope.com https://api.themetroscope.com; frame-ancestors 'self';" always;`
- [x] **Rate Limiting & Telemetry Protection (Verified in Codebase):**
  - [x] API rate limiting zone configured: `limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;`.
  - [x] `/health/ops` and `/social/facebook/status` protected by `verify_operator_auth`.
  - [x] `/photo-cards/articles/{id}/render` protected by operator auth and 30 req/min rate limit.

---

## 4. Environment Variables & Secrets Management

- [ ] **File Permissions (To execute on production host):**
  - [ ] Production `.env` file permissions set to `chmod 600 .env` (readable and writable only by the deployment user).
  - [ ] Owner set to non-root deployer: `chown deployer:deployer .env`.
- [x] **Secret Entropy & Generation (Documented in `.env.example`):**
  - [x] `POSTGRES_PASSWORD`: Must be generated using a secure 32+ character random string (e.g., `openssl rand -base64 32`).
  - [x] `SECRET_KEY`: High-entropy 32+ character random secret required. Default salt explicitly rejected in production.
  - [x] `OPERATOR_API_KEY`: Dedicated 64-character secret token for internal API operations.
- [x] **Production Domain Mapping (Verified in Codebase):**
  - [x] `SITE_URL=https://themetroscope.com`
  - [x] `NEXT_PUBLIC_SITE_URL=https://themetroscope.com`
  - [x] `NEXT_PUBLIC_API_URL=https://api.themetroscope.com`
  - [x] `ALLOWED_HOSTS="themetroscope.com,api.themetroscope.com,www.themetroscope.com,localhost,127.0.0.1"`
  - [x] `BACKEND_CORS_ORIGINS=["https://themetroscope.com","https://www.themetroscope.com","https://api.themetroscope.com"]`
- [x] **Social Publishing Safety Locks (Verified in Codebase):**
  - [x] Confirmed `FACEBOOK_AUTO_PUBLISH=false`.
  - [x] Confirmed `FACEBOOK_ENABLED=false`.
  - [x] Confirmed `SOCIAL_PUBLISHING_ENABLED=false`.

---

## 5. Database Layer & Backups

- [x] **Database Account Hardening (Verified in Codebase):**
  - [x] Database configuration specifies dedicated `POSTGRES_USER` and credentials.
- [ ] **Automated Backups (To configure on host):**
  - [ ] Daily encrypted PostgreSQL database dumps configured via cron:
    ```bash
    docker compose exec -T db pg_dump -U postgres metroscope | gzip | gpg --encrypt -r operator@themetroscope.com > /var/backups/metroscope_$(date +%Y%m%d).sql.gz.gpg
    ```
  - [ ] Offsite backup replication to encrypted AWS S3 bucket with 30-day lifecycle expiration policy.
- [ ] **Migration Verification (To execute on host):**
  - [ ] Execute `alembic upgrade head` inside container before routing public traffic.

---

## 6. Monitoring, Logging & Incident Readiness

- [ ] **Log Retention & Rotation:**
  - [ ] Configure Docker daemon log rotation in `/etc/docker/daemon.json`:
    ```json
    {
      "log-driver": "json-file",
      "log-opts": {
        "max-size": "50m",
        "max-file": "5"
      }
    }
    ```
- [x] **Log Sanitization (Verified in Codebase):**
  - [x] Verified application logs do not print raw API tokens, Facebook access tokens, or database passwords.
- [ ] **Uptime & Health Monitoring:**
  - [ ] External uptime monitor pinging `https://api.themetroscope.com/health/ready`.
- [ ] **Rollback Procedure:**
  - [ ] Verified rollback procedure documented in case of emergency rollback:
    1. Stop containers: `docker compose -f docker-compose.prod.yml down`
    2. Restore previous database snapshot.
    3. Checkout previous release tag and restart.
