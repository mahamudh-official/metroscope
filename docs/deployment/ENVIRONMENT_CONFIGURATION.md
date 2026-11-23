# MetroScope — Environment Configuration Reference

This document details all configuration options for MetroScope across all application tiers and phases.

## 1. Environment Variable Reference

### Application & Runtime Environment

| Variable | Type | Default | Production Value | Description |
| :--- | :---: | :---: | :---: | :--- |
| `ENVIRONMENT` | string | `development` | `production` | Active deployment environment name |
| `DEBUG` | boolean | `true` | `false` | Enables debug traceback and OpenAPI docs. Must be `false` in production. |
| `LOG_LEVEL` | string | `INFO` | `INFO` | Logging threshold (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `PROJECT_NAME` | string | `MetroScope` | `MetroScope` | Application brand name |
| `API_V1_STR` | string | `/api/v1` | `/api/v1` | Root URL prefix for v1 API endpoints |

### Networking, Trusted Hosts & CORS

| Variable | Type | Default | Production Value | Description |
| :--- | :---: | :---: | :---: | :--- |
| `SITE_URL` | string | `https://metroscope.news` | `https://metroscope.news` | Public canonical base URL for external links and sitemaps |
| `NEXT_PUBLIC_SITE_URL` | string | `http://localhost:3000` | `https://metroscope.news` | Frontend public origin |
| `NEXT_PUBLIC_API_URL` | string | `http://localhost:8000/api/v1` | `https://metroscope.news/api/v1` | Browser-accessible API endpoint |
| `ALLOWED_HOSTS` | list | `["localhost", ...]` | `["metroscope.news", "www.metroscope.news", "backend", "localhost", "127.0.0.1"]` | Trusted host headers accepted by backend |
| `BACKEND_CORS_ORIGINS` | list | `["http://localhost:3000"]` | `["https://metroscope.news", "https://www.metroscope.news"]` | Allowed CORS origins |

### PostgreSQL Database

| Variable | Type | Default | Production Value | Description |
| :--- | :---: | :---: | :---: | :--- |
| `POSTGRES_SERVER` | string | `localhost` | `db` | Docker service name of database |
| `POSTGRES_PORT` | integer | `5432` | `5432` | Internal database port |
| `POSTGRES_DB` | string | `metroscope` | `metroscope` | Database name |
| `POSTGRES_USER` | string | `metroscope_user` | `metroscope_user` | Database user |
| `POSTGRES_PASSWORD` | string | `metroscope_secure_password` | *(Random 32+ chars)* | Master database password |
| `DATABASE_URL` | string | *(derived)* | `postgresql+asyncpg://...` | Asynchronous SQLAlchemy connection string |
| `DATABASE_SYNC_URL` | string | *(derived)* | `postgresql://...` | Synchronous connection string for Alembic |

> [!TIP]
> Generate a cryptographically strong database password on Ubuntu:
> ```bash
> openssl rand -hex 24
> ```

### News Ingestion Worker (GDELT)

| Variable | Type | Default | Production Value | Description |
| :--- | :---: | :---: | :---: | :--- |
| `GDELT_BASE_URL` | string | `https://api.gdeltproject.org/api/v2/doc/doc` | `https://api.gdeltproject.org/api/v2/doc/doc` | GDELT DOC 2.0 ArtList endpoint |
| `GDELT_POLL_INTERVAL_MINUTES` | integer | `15` | `15` | Background ingestion polling frequency |
| `GDELT_REQUEST_TIMEOUT_SECONDS`| float | `15.0` | `15.0` | Network timeout for GDELT API calls |
| `GDELT_MAX_RETRIES` | integer | `3` | `3` | Exponential backoff attempts |
| `WORKER_ENABLED` | boolean | `true` | `true` | Enables background APScheduler worker |

### Automated Social Publishing (Phase 5)

| Variable | Type | Default | Production Value | Description |
| :--- | :---: | :---: | :---: | :--- |
| `SOCIAL_PUBLISHING_ENABLED` | boolean | `false` | `false` (until configured) | Master switch for social posting |
| `SOCIAL_DRY_RUN` | boolean | `true` | `true` | Simulates social publishing without making live API calls |
| `SOCIAL_PUBLISHING_INTERVAL_MINUTES` | integer | `30` | `30` | Execution frequency |
| `SOCIAL_MAX_POSTS_PER_RUN` | integer | `2` | `2` | Maximum articles posted per run |
| `SOCIAL_MIN_QUALITY_SCORE` | float | `70.0` | `70.0` | Minimum editorial quality score |
| `FACEBOOK_ENABLED` | boolean | `false` | `false` | Meta Graph API publisher switch |
| `FACEBOOK_PAGE_ID` | string | `None` | *(Page ID)* | Meta Page Identifier |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | string | `None` | *(Token)* | Long-lived Page Access Token |
| `X_ENABLED` | boolean | `false` | `false` | X API v2 publisher switch |
| `X_API_KEY` | string | `None` | *(API Key)* | X Consumer Key |
| `X_API_SECRET` | string | `None` | *(Secret)* | X Consumer Secret |
| `X_ACCESS_TOKEN` | string | `None` | *(Token)* | X OAuth 1.0a User Access Token |
| `X_ACCESS_TOKEN_SECRET` | string | `None` | *(Secret)* | X OAuth 1.0a User Access Secret |
| `X_MAX_POSTS_PER_DAY` | integer | `15` | `15` | Rolling 24h limit respecting X Free tier (17/24h) |

### Email Subscription & Newsletter Delivery (Phase 6)

| Variable | Type | Default | Production Value | Description |
| :--- | :---: | :---: | :---: | :--- |
| `EMAIL_DRY_RUN` | boolean | `true` | `true` (default safe mode) | Simulates email sending without opening SMTP connection |
| `SMTP_HOST` | string | `localhost` | *(e.g. smtp.sendgrid.net)* | Remote SMTP host |
| `SMTP_PORT` | integer | `587` | `587` | SMTP port |
| `SMTP_USERNAME` | string | `None` | *(SMTP username/apikey)* | SMTP authentication user |
| `SMTP_PASSWORD` | string | `None` | *(SMTP password/secret)* | SMTP authentication secret |
| `SMTP_FROM_EMAIL` | string | `newsletter@metroscope.news` | `newsletter@metroscope.news` | Sender email address |
| `SMTP_FROM_NAME` | string | `MetroScope News` | `MetroScope News` | Sender display name |
| `SMTP_USE_TLS` | boolean | `true` | `true` | Enforces STARTTLS encryption |
| `NEWSLETTER_SCHEDULE_HOUR` | integer | `6` | `6` | Daily dispatch UTC hour (06:00 UTC) |
| `NEWSLETTER_SCHEDULE_MINUTE` | integer | `0` | `0` | Daily dispatch UTC minute |
| `NEWSLETTER_MIN_QUALITY_SCORE` | float | `70.0` | `70.0` | Minimum score for newsletter inclusion |
| `NEWSLETTER_MAX_ARTICLES` | integer | `5` | `5` | Stories included per briefing |
| `SUBSCRIPTION_RATE_LIMIT_PER_HOUR` | integer | `5` | `5` | Anti-spam subscription threshold |
| `VERIFICATION_TOKEN_EXPIRE_HOURS` | integer | `24` | `24` | Expiration window for double opt-in |

---

## 2. Production Security Audit Checks

When `ENVIRONMENT=production`, the application performs automated checks at startup:
- **DEBUG Check**: Rejects `DEBUG=true` in production mode.
- **Default Password Check**: Detects if default sample `POSTGRES_PASSWORD` is used.
- **Dry-Run Enforcement**: Confirms dry-run status and warns if live sending is active without remote credentials.
- **File Permissions**: The `.env` file on the production host must be locked down:
  ```bash
  chmod 600 /opt/metroscope/.env
  ```
