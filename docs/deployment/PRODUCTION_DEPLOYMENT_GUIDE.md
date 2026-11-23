# MetroScope — Production Deployment Guide

## 1. Overview & Architecture

MetroScope is deployed as a coordinated set of lightweight Docker containers orchestrated by **Docker Compose** on a single **AWS EC2 `t3.small`** instance running Ubuntu Server 24.04 LTS in Mumbai (`ap-south-1`).

### Approved Production Topology

```
Public Internet (HTTPS / HTTP)
       │
       ▼ (Ports 80, 443)
┌──────────────────────────────────────────────────────────────┐
│ AWS EC2 t3.small (ap-south-1) — 2 vCPU, 2 GiB RAM, 30 GB gp3 │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                    Nginx Reverse Proxy                 │  │
│  │      - Port 80: Let's Encrypt challenge & HTTP         │  │
│  │      - Port 443: TLS 1.2/1.3 with Mozilla Intermediate │  │
│  │      - Rate limits: API (15 r/s), Subscribe (3 r/s)    │  │
│  │      - Memory Limit: 128 MB                            │  │
│  └───────────────┬────────────────────────┬───────────────┘  │
│                  │ (internal)             │ (internal)       │
│                  ▼                        ▼                  │
│  ┌────────────────────────┐    ┌──────────────────────────┐  │
│  │ Next.js 14 Frontend    │    │ FastAPI Backend API      │  │
│  │  - Node.js 20 Alpine   │    │  - Python 3.11 Slim      │  │
│  │  - Standalone output   │    │  - Uvicorn ASGI Server   │  │
│  │  - Port 3000           │    │  - Port 8000             │  │
│  │  - Memory: 256 MB      │    │  - Memory: 384 MB        │  │
│  └────────────────────────┘    └──────────┬───────────────┘  │
│                                           │ (asyncpg)        │
│  ┌────────────────────────┐               │                  │
│  │ News Ingestion Worker  │               ▼                  │
│  │  - APScheduler 3.10    │    ┌──────────────────────────┐  │
│  │  - GDELT Poller (15m)  │    │ PostgreSQL 16 Alpine     │  │
│  │  - Social Pub (30m)    │───▶│  - Port 5432 (Internal)  │  │
│  │  - Newsletter (06:00)  │    │  - Tuned buffers (128MB) │  │
│  │  - Memory: 256 MB      │    │  - Persistent Volume     │  │
│  └────────────────────────┘    │  - Memory: 384 MB        │  │
│                                └──────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
Total Container Memory Limit: 1,408 MB (Host retains ~640 MB)
```

---

## 2. Pre-Deployment Checklist

Before deploying MetroScope to production:

- [ ] EC2 `t3.small` provisioned in Mumbai (`ap-south-1`) with 30 GB gp3 storage.
- [ ] Security Group allows inbound traffic **strictly** on:
  - Port 22 (SSH — restricted to admin IP/CIDR).
  - Port 80 (HTTP — public).
  - Port 443 (HTTPS — public).
  - **Port 5432 is strictly private** (no external inbound rule).
- [ ] DNS `A` records point `metroscope.news` and `www.metroscope.news` to the EC2 Elastic IP.
- [ ] GitHub Repository Secrets configured:
  - `EC2_HOST`: Elastic IP or public hostname.
  - `EC2_USER`: `ubuntu`.
  - `EC2_SSH_PRIVATE_KEY`: OpenSSH private key for passwordless deployment.
  - `GHCR_PULL_TOKEN`: Personal Access Token with `read:packages` scope (if private).
- [ ] Production `.env` file created on the server at `/opt/metroscope/.env` with strong random passwords.

---

## 3. Automated CI/CD Deployment Flow

Deployments are executed automatically via GitHub Actions upon pushing to the `main` branch or pushing a semantic release tag (`v*.*.*`):

1. **Verify**: Runs full unit & integration tests (`pytest`), ESLint, TypeScript check (`tsc --noEmit`), Next.js production build, and Docker Compose schema validation.
2. **Build & Push**: Builds multi-stage production images, tags with immutable commit SHA (`${{ github.sha }}`) and `latest`, and publishes to GitHub Container Registry (`ghcr.io`).
3. **Deploy**: Connects to the EC2 instance via SSH, updates local repository, runs `./scripts/deploy.sh`, executes database migrations (`alembic upgrade head`), starts containers with rolling update, and validates health probes.
4. **Automated Rollback**: If health probes fail post-deployment, `./scripts/rollback.sh` is automatically triggered.

---

## 4. Manual Deployment Procedure

To deploy manually or perform initial bootstrap on the EC2 instance:

```bash
# 1. SSH into the instance
ssh -i ~/.ssh/metroscope_key.pem ubuntu@<EC2_ELASTIC_IP>

# 2. Navigate to project root
cd /opt/metroscope

# 3. Pull latest git commits
git pull origin main

# 4. Verify environment file exists
if [ ! -f .env ]; then
    echo "ERROR: .env missing. Copy .env.production.template and set strong passwords."
    exit 1
fi

# 5. Make deployment scripts executable
chmod +x scripts/*.sh

# 6. Execute deployment
./scripts/deploy.sh

# 7. Run diagnostic verification
./scripts/validate_deployment.sh
```

---

## 5. Post-Deployment Verification

Verify all services are healthy and responsive:

```bash
# Check container status and resource consumption
docker compose -f docker-compose.prod.yml ps
docker stats --no-stream

# Verify backend health probes
curl -I http://localhost:8000/health/ready
curl -s http://localhost:8000/health/metrics | jq .

# Verify frontend responses
curl -I http://localhost:3000/
curl -I http://localhost:3000/verify-subscription
curl -I http://localhost:3000/unsubscribe

# Verify Nginx reverse proxy
curl -I http://localhost/health
```
