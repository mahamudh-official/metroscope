# MetroScope Environment Configuration & Setup Guide

This document describes the environment variables required to configure MetroScope across local development, Docker Compose, and production environments.

## 1. Environment Variable Reference

| Variable Name | Required | Default (Development) | Purpose |
|---|---|---|---|
| `ENVIRONMENT` | Yes | `development` | Runtime mode: `development`, `test`, or `production`. |
| `DEBUG` | No | `true` | Enables FastAPI debug logs and Swagger/Redoc endpoints. |
| `LOG_LEVEL` | No | `INFO` | Logging threshold (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `POSTGRES_SERVER` | Yes | `localhost` | Database host (use `db` in Docker Compose). |
| `POSTGRES_PORT` | No | `5432` | Database port. |
| `POSTGRES_DB` | Yes | `metroscope` | Database name. |
| `POSTGRES_USER` | Yes | `metroscope_user` | Database user. |
| `POSTGRES_PASSWORD` | Yes | `metroscope_secure_password` | Database user password. |
| `DATABASE_URL` | No | Constructed from above | Async connection URL for FastAPI (`postgresql+asyncpg://...`). |
| `DATABASE_SYNC_URL` | No | Constructed from above | Sync connection URL for Alembic migrations (`postgresql://...`). |
| `BACKEND_HOST` | No | `0.0.0.0` | FastAPI binding host. |
| `BACKEND_PORT` | No | `8000` | FastAPI binding port. |
| `BACKEND_CORS_ORIGINS` | No | `["http://localhost:3000"]` | Allowed CORS origins as a JSON array or comma list. |
| `NEXT_PUBLIC_APP_NAME` | No | `MetroScope` | Application brand name used by the frontend. |
| `NEXT_PUBLIC_SITE_URL` | No | `http://localhost:3000` | Canonical site URL for OpenGraph and SEO tags. |
| `NEXT_PUBLIC_API_URL` | No | `http://localhost:8000/api/v1` | Public API endpoint for frontend requests. |
| `GDELT_BASE_URL` | No | `https://api.gdeltproject.org/api/v2/doc/doc` | Primary GDELT DOC 2.0 API endpoint. |
| `GDELT_REQUEST_TIMEOUT_SECONDS` | No | `15` | Timeout for outbound GDELT HTTP calls. |
| `GDELT_MAX_RETRIES` | No | `3` | Exponential backoff retry attempts for GDELT API. |
| `GDELT_POLL_INTERVAL_MINUTES` | No | `15` | APScheduler interval between discovery cycles. |
| `WORKER_ENABLED` | No | `true` | Toggles background news worker on or off. |

## 2. Local Development Setup

### Quick Setup with `.env`

Copy the template file to `.env`:

```bash
cp .env.example .env
```

### Running Backend Locally

Ensure Python 3.11+ is installed.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Running Frontend Locally

Ensure Node.js 20+ is installed.

```bash
cd frontend
npm install
npm run dev
```

Visit [http://localhost:3000](http://localhost:3000) in your browser.

### Running News Worker Locally

In a separate terminal:

```bash
cd backend
source .venv/bin/activate
python -m app.workers.main
```

## 3. Docker Compose Orchestration

To run the complete platform including PostgreSQL, Backend, Worker, Frontend, and Nginx reverse proxy:

```bash
docker compose up -d --build
```

Verify service status:

```bash
docker compose ps
docker compose logs -f backend
```

## 4. Production Host Requirements (AWS EC2 t3.small — 2 GB RAM)

Because the t3.small EC2 instance operates with 2 GB RAM, configure a 2 GB to 4 GB swapfile on Ubuntu Server 24.04 LTS to prevent Linux kernel Out-Of-Memory (OOM) kills during temporary workload surges:

```bash
# Create 2GB swap space on host
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Persist swapfile across reboots
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Verify swap status
sudo swapon --show
free -h
```

Container memory limits are strictly constrained in `docker-compose.yml`:
- `db`: 384 MB
- `backend`: 384 MB
- `worker`: 256 MB
- `frontend`: 256 MB
- `nginx`: 128 MB
**Total Container Allocations:** ~1,408 MB (leaving >600 MB dedicated for Ubuntu kernel, systemd, and Docker daemon).
