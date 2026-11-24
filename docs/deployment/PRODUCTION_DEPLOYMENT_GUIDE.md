# MetroScope — Production Deployment Guide

## 1. Overview & Architecture

MetroScope is deployed as a coordinated set of lightweight Docker containers orchestrated by **Docker Compose** on an **AWS EC2 `t3.small`** instance running Ubuntu Server 24.04 LTS in Sydney (`ap-southeast-2`).

### Target Deployment Environment

| Item | Specification |
|---|---|
| **Cloud Provider** | AWS EC2 |
| **Region** | `ap-southeast-2` (Sydney) |
| **Instance Type** | `t3.small` (2 vCPU, 2 GiB RAM, 30 GiB gp3) |
| **Operating System** | Ubuntu Server 24.04 LTS |
| **Deployment Root** | `/srv/metroscope/app` |
| **Domain** | `themetroscope.com` (Canonical: `https://themetroscope.com`) |
| **Git Repository** | `mahamudh-official/metroscope` |
| **Deployment Branch** | `master` |
| **Timezone** | `Asia/Dhaka` |

### Server Directory Structure

```text
/srv/metroscope/
├── app/                  # Application repository checkout & Compose stack
├── backups/              # Tiered backups (daily/, weekly/, monthly/)
├── config/               # Host-level configuration
├── data/
│   ├── media/
│   ├── photo-cards/
│   └── postgres/         # Persistent PostgreSQL data directory (UID 70:70, chmod 700)
└── secrets/              # Restricted host secrets (chmod 700)
```

---

## 2. Controlled Manual Deployment Policy

In accordance with MetroScope's security policy:
- **No Automatic SSH Deployment on Push**: Code pushes to `master` do **not** trigger automatic deployment to production.
- **Continuous Integration (CI)**: GitHub Actions executes linting, typechecking, tests, and compose validation.
- **Manual Image Building**: The `deploy-production.yml` workflow triggers on `workflow_dispatch` to build and push verified immutable containers to GitHub Container Registry (`ghcr.io/mahamudh-official/metroscope/*`).
- **Controlled Host Deployment**: Deployments on EC2 are performed manually by the operator using `git pull origin master` and `./scripts/deploy.sh`.

---

## 3. Safe Two-Stage Deployment & TLS Bootstrap

To prevent startup failures caused by missing SSL certificates, deployment follows a strict two-stage process:

### Stage A: HTTP Bootstrap (Initial Deployment)
1. Nginx starts using `infrastructure/nginx/conf.d/metroscope.conf`.
2. Serves HTTP traffic on port 80 and handles Let's Encrypt ACME challenges at `/.well-known/acme-challenge/`.
3. Starts core services: `db`, `backend`, `frontend`, `nginx`.
4. **Worker service is explicitly stopped** (safety policy: no automated ingestion or social posting during initial launch).
5. Certbot can now verify domain ownership and obtain the initial certificate.

### Stage B: HTTPS Activation
1. Run `./scripts/enable_ssl.sh` after DNS `A` records point to the EC2 Elastic IP.
2. Certbot obtains the certificate for `themetroscope.com`, `www.themetroscope.com`, and `api.themetroscope.com`.
3. Activates `metroscope-ssl.conf` (HSTS, TLS 1.2/1.3, HTTP-to-HTTPS redirect).
4. Verifies Nginx configuration syntax (`nginx -t`) and reloads Nginx gracefully.

---

## 4. Initial Production Deployment Procedure (Step-by-Step)

### Step 1: Connect to the Server
```bash
ssh -i ~/.ssh/metroscope_key.pem ubuntu@<EC2_ELASTIC_IP>
```

### Step 2: Prepare Host Persistent Directory
Ensure `/srv/metroscope/data/postgres` is prepared with the correct PostgreSQL Alpine UID/GID (70:70):
```bash
sudo chown -R 70:70 /srv/metroscope/data/postgres
sudo chmod 700 /srv/metroscope/data/postgres
```

### Step 3: Clone or Update Repository
```bash
cd /srv/metroscope/app

# If initial setup:
# git clone -b master https://github.com/mahamudh-official/metroscope.git .

# If updating existing deployment:
git fetch origin master
git checkout master
git pull origin master
```

### Step 4: Configure Production Environment
Copy the production template and generate cryptographically secure secrets:
```bash
cp .env.production.template .env
chmod 600 .env

# Generate secure secrets:
# OPERATOR_API_KEY (min 32 chars): openssl rand -hex 32
# SECRET_KEY (min 32 chars): openssl rand -hex 32
# POSTGRES_PASSWORD (min 24 chars): openssl rand -hex 24
nano .env
```

Ensure safety defaults remain enforced:
```env
WORKER_ENABLED=false
WEBZ_IO_COLLECTION_ENABLED=false
SOCIAL_PUBLISHING_ENABLED=false
SOCIAL_DRY_RUN=true
FACEBOOK_ENABLED=false
FACEBOOK_AUTO_PUBLISH=false
X_ENABLED=false
EMAIL_DRY_RUN=true
```

### Step 5: Authenticate with GHCR (If Images are Private)
```bash
echo "<YOUR_GITHUB_PAT>" | sudo docker login ghcr.io -u "<YOUR_GITHUB_USER>" --password-stdin
```

### Step 6: Execute Deployment Script
```bash
chmod +x scripts/*.sh
./scripts/deploy.sh
```
This script:
1. Validates the Docker Compose configuration.
2. Pulls target image tags for `backend`, `frontend`, `nginx`, and `db`.
3. Starts `db` and waits for PostgreSQL health.
4. Executes Alembic database migrations (`alembic upgrade head`).
5. Starts `backend`, `frontend`, and `nginx`.
6. Executes service-aware health checks across the internal network.
7. Leaves `worker` stopped.

### Step 7: Validate Deployment Health
```bash
./scripts/validate_deployment.sh
```

### Step 8: Activate HTTPS / SSL (Once DNS is Live)
Once DNS `A` records for `themetroscope.com`, `www.themetroscope.com`, and `api.themetroscope.com` resolve to the instance IP:
```bash
./scripts/enable_ssl.sh admin@themetroscope.com
```

### Step 9: Configure Automated Backups
Install the daily backup cron job:
```bash
crontab -e
# Add:
30 2 * * * /srv/metroscope/app/scripts/backup_postgres.sh >> /srv/metroscope/backups/cron.log 2>&1
```

---

## 5. Rollback Procedure

If any issue occurs, invoke the emergency rollback script:
```bash
cd /srv/metroscope/app
./scripts/rollback.sh
```
The script pulls the previous verified release tag recorded in `.last_deployed_version`, restarts `backend`, `frontend`, and `nginx`, and validates health probes. Database volumes and data are never deleted.
