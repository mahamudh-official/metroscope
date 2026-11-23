# METROSCOPE — LOCAL TESTING GUIDE
## Manual Testing & Local Operations Manual for Project Owner

**Document Version:** `1.0.0`  
**Target Audience:** Project Owner & Development Team  
**Last Updated:** `2026-11-08`  

---

## 1. REQUIRED SOFTWARE

Before running MetroScope locally, ensure the following core software runtimes are installed on your workstation:

| Runtime / Tool | Minimum Version | Recommended / Installed Version | Purpose |
| :--- | :---: | :---: | :--- |
| **Node.js** | `v18.17+` | `v20.x` LTS or `v22.x` | Next.js 14 Frontend Standalone Server & SSR |
| **Python** | `3.11+` | `3.11` / `3.12` / `3.14` | FastAPI Backend API & APScheduler Background Worker |
| **PostgreSQL** | `16+` | `18.4` (or `16-alpine` via Docker) | Primary Relational Database & Full-Text Search Engine |
| **PowerShell** | `5.1+` | `7.x` or Windows PowerShell `5.1` | Native Windows one-command automation scripts |
| **Bash** *(Optional)* | `4.0+` | Git Bash / WSL2 / Ubuntu 24.04 | Linux / macOS / Git Bash operational scripts |
| **Docker & Compose** *(Optional)* | `24.0+` | `Docker 28.x` & `Compose v2.38+` | Containerized stack execution (if using Docker) |

---

## 2. INITIAL SETUP

If cloning or checking out the repository on a new machine for the first time:

### 2.1 Backend Dependencies
From the repository root, install Python packages:
```powershell
pip install -r backend/requirements.txt
```

### 2.2 Frontend Dependencies
From the repository root, install Node.js dependencies:
```powershell
cd frontend
npm ci
cd ..
```

---

## 3. ENVIRONMENT FILE SETUP

MetroScope includes a ready-to-use local configuration file (`.env`). If `.env` is not present, the startup script will automatically create one from `.env.example`.

To manually create or inspect the environment configuration:
```powershell
# Copy the template
Copy-Item .env.example .env
```

### Key Local Settings Explained:
- `ENVIRONMENT=development`: Enables local development behavior, debug logging, and local CORS origins.
- `SITE_URL=http://localhost:3000`: Base website URL for internal links and Open Graph previews.
- `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`: Public API endpoint consumed by the browser.
- `INTERNAL_API_URL=http://127.0.0.1:8000/api/v1`: Internal server-side API endpoint for Next.js SSR.
- `POSTGRES_PORT=5433`: Port for the local PostgreSQL development database (`.postgres_runtime`).
- `DATABASE_URL=postgresql+asyncpg://metroscope_user:metroscope_secure_password@127.0.0.1:5433/metroscope`: Managed connection string.
- `SOCIAL_DRY_RUN=true`: **MANDATORY SAFETY FLAG.** Ensures 0 real posts are published to Facebook or X.
- `EMAIL_DRY_RUN=true`: **MANDATORY SAFETY FLAG.** Ensures 0 real emails are dispatched to external SMTP servers.
- `WORKER_ENABLED=true`: Enables background GDELT polling, quality evaluation, and dry-run tasks.

---

## 4. ONE-COMMAND LOCAL STARTUP

To start the complete MetroScope platform (PostgreSQL, FastAPI Backend, APScheduler Worker, and Next.js Frontend) in a single command:

### On Windows (PowerShell):
```powershell
.\scripts\local_start.ps1
```
*(If script execution is restricted on your machine, run: `powershell -ExecutionPolicy Bypass -File .\scripts\local_start.ps1`)*

### On Linux / macOS / Git Bash:
```bash
./scripts/local_start.sh
```

### What Happens Automatically:
1. Validates `.env` and runtime directories (`logs/`, `.pids/`).
2. Starts PostgreSQL using `.postgres_runtime` on port 5433 (or detects already running instance).
3. Safely checks and applies pending Alembic database migrations up to `HEAD`.
4. Starts FastAPI backend on `http://127.0.0.1:8000`.
5. Starts the APScheduler background worker daemon.
6. Starts the Next.js frontend on `http://localhost:3000`.
7. Probes readiness endpoints and displays clickable local URLs in the console.

---

## 5. LOCAL ACCESS URLS

Once the startup command finishes, open your web browser to any of the following URLs:

| Service / Interface | Local URL | Description |
| :--- | :--- | :--- |
| **MetroScope Front Page** | [`http://localhost:3000`](http://localhost:3000) | Primary user-facing news discovery website |
| **World News Category** | [`http://localhost:3000/category/world`](http://localhost:3000/category/world) | World news feed with editorial clustering |
| **Business Category** | [`http://localhost:3000/category/business`](http://localhost:3000/category/business) | Financial and business news |
| **Technology Category** | [`http://localhost:3000/category/technology`](http://localhost:3000/category/technology) | Technology news |
| **News Search Archive** | [`http://localhost:3000/search?q=news`](http://localhost:3000/search?q=news) | Interactive search interface |
| **FastAPI Interactive Docs** | [`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs) | Swagger UI for exploring backend REST endpoints |
| **FastAPI Health Probe** | [`http://127.0.0.1:8000/health`](http://127.0.0.1:8000/health) | System health status and database connectivity |
| **Operational Metrics** | [`http://127.0.0.1:8000/health/metrics`](http://127.0.0.1:8000/health/metrics) | Real-time article and subscriber statistics |

---

## 6. HOW TO STOP THE APPLICATION

To cleanly shut down all MetroScope background processes without deleting or resetting any database records:

### On Windows (PowerShell):
```powershell
.\scripts\local_stop.ps1
```

### On Linux / macOS / Git Bash:
```bash
./scripts/local_stop.sh
```

This stops the Frontend, Worker, Backend, and PostgreSQL processes and releases ports `3000`, `8000`, and `5433`.

---

## 7. HOW TO RESTART THE APPLICATION

To perform a clean restart:
```powershell
# 1. Stop all running services
.\scripts\local_stop.ps1

# 2. Start services fresh
.\scripts\local_start.ps1
```

---

## 8. HOW TO INSPECT APPLICATION LOGS

All background logs are stored in the `logs/` directory. You can inspect them using the log utility script or directly via PowerShell / Bash:

### Using the Log Utility Script:
```powershell
# View recent logs from all services (default 30 lines)
.\scripts\local_logs.ps1

# View specific service logs:
.\scripts\local_logs.ps1 -Service backend
.\scripts\local_logs.ps1 -Service worker
.\scripts\local_logs.ps1 -Service frontend
.\scripts\local_logs.ps1 -Service postgres

# Follow live output in real-time (like tail -f):
.\scripts\local_logs.ps1 -Service backend -Follow
```

### Direct File Inspection:
- Backend log: `Get-Content logs\backend.log -Tail 50 -Wait`
- Worker log: `Get-Content logs\worker.log -Tail 50 -Wait`
- Frontend log: `Get-Content logs\frontend.log -Tail 50 -Wait`
- PostgreSQL log: `Get-Content logs\postgres.log -Tail 50`

---

## 9. HOW TO VERIFY DATABASE CONNECTIVITY

### Quick Check:
Run the status script:
```powershell
.\scripts\local_status.ps1
```
Expected output:
```
  PostgreSQL Database : ONLINE (Port 5433 - .postgres_runtime)
  FastAPI Backend API : HEALTHY (Port 8000)
  Next.js Frontend    : READY (Port 3000)
  Background Worker   : RUNNING (PID: ...)
```

### Direct PostgreSQL Query:
Using `psql`:
```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h 127.0.0.1 -p 5433 -U metroscope_user -d metroscope -c "SELECT current_database(), count(*) FROM news_articles;"
```

---

## 10. HOW TO TEST GDELT INGESTION

1. When the application is running, the APScheduler worker automatically polls GDELT every 15 minutes.
2. To trigger an immediate manual GDELT ingestion cycle:
   ```powershell
   $env:PYTHONPATH="backend"
   $env:DATABASE_URL="postgresql+asyncpg://metroscope_user:metroscope_secure_password@127.0.0.1:5433/metroscope"
   python -c "import asyncio; from app.workers.jobs import run_gdelt_ingestion_job; asyncio.run(run_gdelt_ingestion_job())"
   ```
3. Check `logs/worker.log` to observe article ingestion, URL normalization, quality scoring, and deduplication.
4. Refresh `http://localhost:3000` in your browser to see newly ingested articles.
5. If offline or GDELT is unreachable, the site continues serving previously persisted database articles normally.

---

## 11. HOW TO TEST NEWSLETTER SUBSCRIPTION (DRY-RUN)

1. Open `http://localhost:3000` in your browser.
2. Scroll to the footer newsletter form.
3. Enter any test email address (e.g. `tester@example.com`) and click **Subscribe**.
4. Observe the instant user-facing confirmation: *"Please check your inbox to confirm your subscription."*
5. Inspect `logs/backend.log` to verify that the verification token was generated and logged without external SMTP traffic.
6. To test confirmation, open:  
   `http://localhost:3000/verify-subscription?token=sample_token`
7. To test unsubscription, open:  
   `http://localhost:3000/unsubscribe?token=sample_token`

---

## 12. HOW TO TEST SOCIAL PUBLISHING (DRY-RUN)

1. Social publishing is configured with `SOCIAL_DRY_RUN=true` to prevent unauthorized external posts.
2. The APScheduler worker runs the social publisher job periodically for articles with editorial quality score $\ge 70.0$.
3. Check `logs/worker.log` for log entries formatted like:
   ```
   [DRY-RUN] Facebook publishing simulated for article #12 ...
   [DRY-RUN] X post simulated: 'Breaking Headline... https://metroscope.news/article/slug'
   ```
4. Verify that `external_post_id` in the database contains `dryrun-fb-...` and `dryrun-x-...` prefixes with 0 real external API calls.

---

## 13. COMMON ERRORS & SOLUTIONS

### Issue 1: "Port 3000 (or 8000, 5433) is already occupied"
- **Cause:** A previous process is still holding the port.
- **Solution:** Run `.\scripts\local_stop.ps1` to terminate lingering processes. Alternatively, check who is using the port via:  
  `Get-NetTCPConnection -LocalPort 3000, 8000, 5433`

### Issue 2: "PostgreSQL: another server might be running / postmaster.pid exists"
- **Cause:** PostgreSQL was previously killed abruptly, leaving a stale lock file.
- **Solution:** `.\scripts\local_start.ps1` detects and automatically cleans stale lock files. You can also manually delete `.postgres_runtime\postmaster.pid`.

### Issue 3: "Next.js: connect ECONNREFUSED 127.0.0.1:8000"
- **Cause:** Next.js started before FastAPI backend was fully listening.
- **Solution:** Verify backend health by opening `http://127.0.0.1:8000/health`. If healthy, refresh the browser at `http://localhost:3000`.

### Issue 4: "PowerShell execution policy blocks script execution"
- **Cause:** Default Windows client restriction on running unsigned `.ps1` scripts.
- **Solution:** Execute with the bypass flag:  
  `powershell -ExecutionPolicy Bypass -File .\scripts\local_start.ps1`

---

## 14. HOW TO PRESERVE DATABASE DATA

- **Location:** All persistent development data is stored in the directory:  
  `c:\Users\Hasan\Documents\metroscope\.postgres_runtime`
- **Safety Rules:**
  - **NEVER** delete the `.postgres_runtime` directory.
  - **NEVER** run `docker compose down -v` (the `-v` flag removes volumes).
  - Use `.\scripts\local_stop.ps1` for clean shutdowns; it stops the database process safely without deleting any files.
- **Creating a Quick Backup:**
  To create a disposable SQL dump of the current database at any time:
  ```powershell
  & "C:\Program Files\PostgreSQL\18\bin\pg_dump.exe" -h 127.0.0.1 -p 5433 -U metroscope_user -d metroscope -F c -f "database_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').dump"
  ```
