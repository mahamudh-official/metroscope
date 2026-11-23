# METROSCOPE — PHASE 11
# LOCAL FINALIZATION & USER HANDOFF REPORT

**Document ID:** `METROSCOPE-PHASE-11-HANDOFF-001`  
**Execution Timestamp:** `2026-11-08T14:04:00+06:00`  
**Target Recipient:** Project Owner & Manual Testing Lead  
**Operating Environment:** Windows Local Production-Ready Runtime (PostgreSQL 18, FastAPI Backend, APScheduler Worker, Next.js 14 Standalone Frontend)  
**Final Status:** **`PHASE 11 COMPLETE — READY FOR OWNER'S LOCAL TESTING`**

---

## 1. EXECUTIVE SUMMARY

Phase 11 finalizes the MetroScope platform for immediate, direct local usage and manual browser testing by the project owner. The entire multi-tier system—encompassing database persistence, automated news ingestion, editorial quality intelligence, full-text search, social media formatting, newsletter double opt-in, and responsive frontend UI—is configured for one-command local startup and clean, safe shutdown.

All existing development database records (`.postgres_runtime` on port 5433) are preserved intact. Both PowerShell (`.ps1`) and Bash (`.sh`) operational scripts have been created to provide zero-friction lifecycle management on Windows and Unix-like environments.

---

## 2. FINAL LOCAL ARCHITECTURE

MetroScope operates locally as a cohesive modular monolith with explicit subsystem boundaries:

```
[ Web Browser / Project Owner ]
              │
              ├───► Next.js 14 SSR Frontend (Port 3000)
              │         │ (Server-Side Fetching / React Server Components)
              │         ▼
              └───► FastAPI REST API Backend (Port 8000)
                        │
                        ├───► PostgreSQL 18 Cluster (Port 5433: .postgres_runtime)
                        │         │ (9 Tables, 47 Indexes, Alembic at HEAD)
                        │         │
                        ▲         ▼
              APScheduler News Worker (Background Daemon)
                  ├── Poller : GDELT DOC 2.0 API (Every 15 min)
                  ├── Social : Facebook & X Publisher (DRY-RUN, Every 30 min)
                  ├── Stale  : Deadlock & Lock Recovery (Every 60 min)
                  └── Brief  : Daily Briefing Newsletter (DRY-RUN, 06:00 UTC)
```

---

## 3. ONE-COMMAND STARTUP & LIFECYCLE SCRIPTS

Four pairs of cross-platform operational scripts have been created in the `scripts/` directory:

| Operation | Windows (PowerShell) | Linux / macOS / Git Bash | Purpose & Behavior |
| :--- | :--- | :--- | :--- |
| **Start Stack** | `.\scripts\local_start.ps1` | `./scripts/local_start.sh` | Validates `.env`, starts DB, runs migrations, starts backend, worker, frontend, probes health, prints URLs. |
| **Stop Stack** | `.\scripts\local_stop.ps1` | `./scripts/local_stop.sh` | Safely terminates all background processes without deleting database files. Verifies port release. |
| **Service Status** | `.\scripts\local_status.ps1` | `./scripts/local_status.sh` | Probes TCP connectivity and HTTP health across all 4 services; prints live article and subscriber metrics. |
| **Inspect Logs** | `.\scripts\local_logs.ps1` | `./scripts/local_logs.sh` | Displays recent logs or streams in follow mode (`-Follow`) for backend, worker, frontend, or database. |

---

## 4. LOCAL ACCESS URLS

The project owner can access and interact with the application through the following URLs:

| Service / Interface | Local URL | Primary Owner Testing Focus |
| :--- | :--- | :--- |
| **MetroScope Front Page** | [`http://localhost:3000`](http://localhost:3000) | Headline grid, trending news carousel, theme toggle, mobile drawer |
| **World News Category** | [`http://localhost:3000/category/world`](http://localhost:3000/category/world) | Category filtering, editorial clustering, relative timestamps |
| **Business Category** | [`http://localhost:3000/category/business`](http://localhost:3000/category/business) | Financial stories, publisher badges, responsive cards |
| **Technology Category** | [`http://localhost:3000/category/technology`](http://localhost:3000/category/technology) | Tech news discovery |
| **Full-Text Search** | [`http://localhost:3000/search?q=news`](http://localhost:3000/search?q=news) | Keyword queries, Unicode / Bangla resilience, empty query state |
| **Article Reading View** | [`http://localhost:3000/article/{slug}`](http://localhost:3000/article/world-news-heavy-rains-flood-70-000-gaza-tents-housing-displaced-people-7949d2ff) | Full article SSR, metadata box, source links, zero mobile overflow |
| **FastAPI Interactive Docs** | [`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs) | Swagger UI for executing and inspecting raw backend endpoints |
| **API Health Status** | [`http://127.0.0.1:8000/health`](http://127.0.0.1:8000/health) | Subsystem health JSON (`database_connected: true`) |
| **Live System Metrics** | [`http://127.0.0.1:8000/health/metrics`](http://127.0.0.1:8000/health/metrics) | Real-time counts of published articles and subscribers |

---

## 5. ENVIRONMENT CONFIGURATION & SAFETY FLAGS

The root `.env` file has been pre-configured specifically for local owner testing:

```ini
ENVIRONMENT=development
DEBUG=true
SITE_URL=http://localhost:3000
NEXT_PUBLIC_SITE_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
INTERNAL_API_URL=http://127.0.0.1:8000/api/v1

# Database Configuration (.postgres_runtime native cluster)
POSTGRES_SERVER=127.0.0.1
POSTGRES_PORT=5433
POSTGRES_DB=metroscope
POSTGRES_USER=metroscope_user
POSTGRES_PASSWORD=metroscope_secure_password
DATABASE_URL=postgresql+asyncpg://metroscope_user:metroscope_secure_password@127.0.0.1:5433/metroscope
DATABASE_SYNC_URL=postgresql://metroscope_user:metroscope_secure_password@127.0.0.1:5433/metroscope

# Strict Safety Dry-Run Enforcements (ZERO EXTERNAL CALLS)
SOCIAL_PUBLISHING_ENABLED=false
SOCIAL_DRY_RUN=true
EMAIL_DRY_RUN=true
WORKER_ENABLED=true
```

### Safety Guarantees:
- **`SOCIAL_DRY_RUN=true`**: Simulated external post IDs generated (`dryrun-fb-...`, `dryrun-x-...`). 0 requests sent to Meta Graph API or X API.
- **`EMAIL_DRY_RUN=true`**: 0 SMTP packets sent to external mail relays. Double opt-in verification tokens generated and logged locally.
- **External GDELT Polling**: Remains active when internet access is available; automatically handles offline mode gracefully without crashing the UI.

---

## 6. DATABASE IDENTITY & PRESERVATION CONFIRMATION

- **Database Engine:** PostgreSQL 18.4 x86_64-windows
- **Physical Cluster Path:** `c:\Users\Hasan\Documents\metroscope\.postgres_runtime`
- **TCP Endpoint:** `127.0.0.1:5433`
- **Database Name:** `metroscope`
- **Alembic Revision:** `0008_email_newsletter` (HEAD)
- **Persisted Data Verified:**
  - `news_articles`: **39 articles** intact
  - `news_sources`: **27 verified publisher sources** intact
  - `email_subscribers`: **0 records** (ready for owner testing)
  - `alembic_version`: **`0008_email_newsletter`**

**Safety Rule:** The `.postgres_runtime` directory must never be deleted. `local_stop.ps1` and `local_stop.sh` stop PostgreSQL gracefully without touching data files.

---

## 7. STARTUP VERIFICATION TEST RESULTS

A complete pre-flight validation pass was executed against the live local stack:

```
==================================================================
APPLICATION STARTUP VALIDATION RESULTS
==================================================================
Health API HTTP Status      : 200 OK
Articles API HTTP Status    : 200 OK
Categories API HTTP Status  : 200 OK
Frontend Homepage Status    : 200 OK
Frontend Category Status    : 200 OK
Backend Health JSON         : {"status":"ok","environment":"development","database_connected":true,"version":"0.1.0"}
Articles Sample Title       : "A year in the life at ACC"
Port 5433 (PostgreSQL)      : Online & Accepting Connections
Port 8000 (FastAPI API)     : Online & Routing Requests
Port 3000 (Next.js SSR)     : Online & Serving Pages
==================================================================
```

---

## 8. KNOWN LIMITATIONS & EXTERNAL CREDENTIAL REQUIREMENTS

The platform is completely functional locally without any paid or third-party credentials. However, the following external integrations are intentionally placed in safe simulated states:

1. **Social Media Live Publishing (`SOCIAL_DRY_RUN=true`):**
   - Requires Meta Graph API Page Access Token (`FACEBOOK_PAGE_ACCESS_TOKEN`) and X Developer API OAuth 1.0a keys (`X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`) before live publishing can be enabled.
   - For owner local testing, dry-run mode simulates publishing and records structured IDs in `social_posts`.
2. **Transactional Email Relay (`EMAIL_DRY_RUN=true`):**
   - Requires Amazon SES or SendGrid SMTP credentials before real outbound emails can be dispatched.
   - For owner local testing, dry-run mode logs verification links directly to `logs/backend.log` and browser feedback is returned immediately.
3. **AWS Deployment:**
   - No AWS credentials or cloud infrastructure are provisioned; all operations are local to the owner's workstation.

---

## 9. STEP-BY-STEP MANUAL TESTING INSTRUCTIONS FOR PROJECT OWNER

The complete manual testing guide is available in [LOCAL_TESTING_GUIDE.md](file:///c:/Users/Hasan/Documents/metroscope/docs/LOCAL_TESTING_GUIDE.md).

### Quick Testing Walkthrough:
1. **Launch MetroScope:**
   ```powershell
   .\scripts\local_start.ps1
   ```
2. **Open Front Page:**
   Navigate to [`http://localhost:3000`](http://localhost:3000). Inspect headlines, image rendering, category sections, and footer.
3. **Test Dark / Light Theme:**
   Click the sun/moon icon in the header. Verify instant color scheme switch without layout shift.
4. **Test Category Browsing:**
   Click "World" or navigate to [`http://localhost:3000/category/world`](http://localhost:3000/category/world). Verify filtered news and publisher badges.
5. **Test News Search:**
   Type a keyword (e.g., `news` or `biden`) into the header search bar and hit Enter. Verify that matching stories render on [`http://localhost:3000/search`](http://localhost:3000/search).
6. **Test Responsive Mobile Navigation:**
   Resize the browser window to mobile width ($< 768$px). Click the hamburger menu icon; verify that the category navigation drawer slides open smoothly.
7. **Test Newsletter Subscription:**
   Scroll to the footer, enter an email address, and click **Subscribe**. Verify the confirmation prompt: *"Please check your inbox to confirm your subscription."*
8. **Inspect Logs & Metrics:**
   Open a separate PowerShell window and run:
   ```powershell
   .\scripts\local_status.ps1
   .\scripts\local_logs.ps1 -Service backend
   ```
9. **Stop When Finished:**
   ```powershell
   .\scripts\local_stop.ps1
   ```

---

## 10. FINAL VERDICT

```
========================================================================================
                          METROSCOPE PHASE 11 VERDICT
========================================================================================
  One-Command Local Startup Scripts      : READY (.\scripts\local_start.ps1 & .sh)
  Safe Local Shutdown Scripts            : READY (.\scripts\local_stop.ps1 & .sh)
  Status & Log Inspection Tools          : READY (.\scripts\local_status.ps1 & logs.ps1)
  Primary Development Database           : VERIFIED (PostgreSQL 18 at .postgres_runtime)
  Database Data Preservation             : 100% INTACT (39 Articles, 27 Sources, HEAD)
  Application Startup Validation         : PASSED (All Endpoints Return HTTP 200 OK)
  Owner's Manual Testing Guide           : PUBLISHED (docs/LOCAL_TESTING_GUIDE.md)
  Dry-Run & External Safety Flags        : ENFORCED (0 External Posts, 0 External Emails)
========================================================================================
  FINAL STATUS: PHASE 11 COMPLETE — READY FOR OWNER'S LOCAL TESTING
========================================================================================
```
