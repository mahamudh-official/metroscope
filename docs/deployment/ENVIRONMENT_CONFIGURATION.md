# MetroScope — Production Environment Configuration Guide

## 1. Overview

Production settings are managed through `/srv/metroscope/app/.env`, generated from `.env.production.template`.

The `.env` file contains sensitive production credentials and **must never be committed to Git**. File permissions must be restricted to `600` (`chmod 600 /srv/metroscope/app/.env`).

---

## 2. Required Production Variables

| Variable | Format / Requirement | Description |
|---|---|---|
| `ENVIRONMENT` | `production` | Enables production validation rules and security middleware |
| `DEBUG` | `false` | Disables interactive debuggers and traceback exposures |
| `SITE_URL` | `https://themetroscope.com` | Canonical site origin for SEO, sitemap, and redirects |
| `ALLOWED_HOSTS` | JSON array of hostnames | Enforced by `TrustedHostMiddleware` |
| `BACKEND_CORS_ORIGINS` | JSON array of origins | Enforced by FastAPI CORS middleware |
| `SECRET_KEY` | Hex string (>= 32 chars) | Application secret key for cryptography |
| `OPERATOR_API_KEY` | Hex string (>= 32 chars) | Mandatory key for operational and photo-card rendering endpoints |
| `POSTGRES_DB` | `metroscope` | PostgreSQL database name |
| `POSTGRES_USER` | `metroscope_user` | PostgreSQL application user |
| `POSTGRES_PASSWORD` | Min 24 chars | Strong database password |
| `POSTGRES_DATA_DIR` | `/srv/metroscope/data/postgres` | Host persistent directory mount |
| `WORKER_ENABLED` | `false` | Safe initial deployment default |
| `WEBZ_IO_COLLECTION_ENABLED` | `false` | Prevents automated ingestion until authorized |
| `SOCIAL_PUBLISHING_ENABLED` | `false` | Prevents automated social publishing |
| `SOCIAL_DRY_RUN` | `true` | Dry-run mode for social publishing |
| `FACEBOOK_ENABLED` | `false` | Prevents automated Facebook publishing |
| `FACEBOOK_AUTO_PUBLISH` | `false` | Prevents auto-publishing |
| `X_ENABLED` | `false` | Prevents automated X publishing |
| `EMAIL_DRY_RUN` | `true` | Prevents automated email delivery |
| `GHCR_REGISTRY` | `ghcr.io` | Container registry host |
| `GHCR_OWNER` | `mahamudh-official` | Repository owner on GitHub |
| `GHCR_REPO` | `metroscope` | GitHub repository name |
| `IMAGE_TAG` | `latest` or git commit SHA | Image tag for production deployment |

---

## 3. Secret Generation Commands

Run these on the EC2 host when preparing `.env`:

```bash
# Generate OPERATOR_API_KEY:
openssl rand -hex 32

# Generate SECRET_KEY:
openssl rand -hex 32

# Generate POSTGRES_PASSWORD:
openssl rand -hex 24
```
