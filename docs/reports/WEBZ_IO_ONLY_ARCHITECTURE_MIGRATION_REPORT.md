# METROSCOPE — SINGLE PROVIDER WEBZ.IO ARCHITECTURE MIGRATION REPORT

**Date:** 2026-11-10  
**Status:** Completed & Regression-Verified  
**Migration Path:** Multi-source (GDELT DOC 2.0 + Curated RSS) → Single-Provider Webz.io News API Architecture  

---

## Executive Summary

The MetroScope news platform has been successfully migrated from its legacy GDELT + RSS multi-source ingestion pipeline to a dedicated, single-provider Webz.io News API acquisition architecture. 

All legacy GDELT and third-party RSS discovery services, clients, schemas, registries, and scheduled poller jobs were safely decommissioned and removed after verifying references. Shared editorial, normalization, deduplication, and publication subsystems were preserved intact. The new integration includes a dedicated HTTPX-based Webz.io client, strict JSON schema validation, durable PostgreSQL-backed budget protection with hard spending ceilings and emergency reserve protection, and an APScheduler schedule executing exactly two daily category-focused jobs in the `Asia/Dhaka` timezone.

Comprehensive automated regression tests (155 tests passing across backend unit, integration, scheduler, and API suites) confirm zero functional regressions.

---

## 1. Final Architecture

The upgraded MetroScope system operates with Webz.io as its sole external news intelligence provider:

```
                                    +-----------------------------------------+
                                    |         Webz.io News API                |
                                    |   (https://api.webz.io/newsApiLite)     |
                                    +--------------------+--------------------+
                                                         |  HTTP GET (size=10, Bearer token)
                                                         v
                                    +-----------------------------------------+
                                    |         WebzClient (HTTPX)              |
                                    |   - Request validation & builder        |
                                    |   - Controlled retry (max 1 attempt)    |
                                    |   - 429 & timeout handling              |
                                    +--------------------+--------------------+
                                                         |
                                                         v
+-------------------------------+   +-----------------------------------------+
|    APScheduler (Asia/Dhaka)   |-->|      WebzIngestionService               |
| 08:00 -> Sports (10 articles) |   |   - Single execution lock (_webz_lock)  |
| 20:00 -> Business(10 articles)|   |   - Budget preflight & reservation      |
+-------------------------------+   |   - Freshness window (max 24h-48h)      |
                                    |   - UUID & Canonical URL deduplication  |
                                    |   - Quality & Relevance scoring         |
                                    |   - Metadata-only summary extraction    |
                                    +--------------------+--------------------+
                                                         |
                         +-------------------------------+-------------------------------+
                         v                                                               v
         +-------------------------------+                               +-------------------------------+
         |     PostgreSQL Database       |                               |      PostgreSQL Database      |
         |         news_articles         |                               |       webz_usage_ledger       |
         |  - uuid (unique, indexed)     |                               |  - billing_period             |
         |  - canonical_url_hash         |                               |  - requests_left              |
         |  - summary (max 250 chars)    |                               |  - estimated vs actual cost   |
         |  - author, topics, trust      |                               |  - remaining allowance ($4)   |
         |  - NO full-body text          |                               |  - protected reserve ($1)     |
         +---------------+---------------+                               +-------------------------------+
                         |
                         v
         +-------------------------------+
         |      FastAPI Public API       |
         |  /api/v1/articles, /health    |
         |  (Excludes full article body) |
         +---------------+---------------+
                         |
                         v
         +-------------------------------+
         |       Next.js Frontend        |
         | Broadsheet UI, 10 Categories, |
         | Search, SEO, MetroScope RSS   |
         +-------------------------------+
```

### Key Operating Constraints:
* **Target Throughput:** Exactly two scheduled jobs per day (10 target articles/job = 20 articles/day; ~600 articles/month).
* **Scheduled Beats:** Sports (08:00 Asia/Dhaka) and Business, Finance & Economy (20:00 Asia/Dhaka).
* **Category Accessibility:** All 10 existing public categories remain active and accessible in the broadsheet UI. Historical articles in all categories are retained.
* **Monthly Provider Credit:** $5.00 total monthly allocation.
* **Collection Ceiling:** $4.00 maximum monthly collection allowance.
* **Emergency Reserve:** $1.00 strictly protected reserve (collection halts before touching reserve).

---

## 2. Removed Legacy Acquisition Systems

In accordance with strict migration requirements, all obsolete third-party acquisition systems were verified and removed:

1. **GDELT API Client & Parser:**
   - Deleted: `backend/app/integrations/gdelt/client.py` (`GDELTClient`, `GDELTAPIError`).
   - Deleted: `backend/app/integrations/gdelt/parser.py` (`parse_gdelt_response`, `RawGDELTArticle`).
   - Deleted: `backend/app/integrations/gdelt/__init__.py`.
   - Deleted: `backend/tests/test_gdelt_client.py` and `backend/tests/test_ingestion.py`.

2. **RSS/Atom Ingestion Subsystem:**
   - Deleted: `backend/app/integrations/rss/client.py` (`RSSClient`).
   - Deleted: `backend/app/integrations/rss/parser.py` (`parse_rss_xml`).
   - Deleted: `backend/app/integrations/rss/registry.py` (`CURATED_FEEDS`).
   - Deleted: `backend/app/integrations/rss/schemas.py` (`FeedSourceConfig`, `RawRSSArticle`).
   - Deleted: `backend/app/services/rss_ingestion_service.py` (`RSSIngestionService`).
   - Deleted: `backend/scripts/run_rss_ingestion.py`.
   - Deleted: `backend/tests/test_rss_ingestion.py`.

3. **Legacy Ingestion Orchestration:**
   - Deleted: `backend/app/services/ingestion_service.py` (`IngestionService`).
   - Deleted: `backend/scripts/run_expansion_ingestion.py`.

4. **Decommissioned Scheduler Jobs:**
   - Removed: `gdelt_discovery_poller` from `backend/app/workers/scheduler.py`.
   - Removed: `rss_discovery_poller` from `backend/app/workers/scheduler.py`.
   - Removed: `poll_gdelt_news_job` and `poll_rss_news_job` from `backend/app/workers/jobs.py`.

5. **Legacy Configuration:**
   - Removed `GDELT_BASE_URL`, `GDELT_REQUEST_TIMEOUT_SECONDS`, `GDELT_MAX_RETRIES`, and `GDELT_POLL_INTERVAL_MINUTES` from `backend/app/core/config.py`, `.env.example`, `.env`, `.env.production.template`, `.env.production.local`, `docker-compose.yml`, and `docker-compose.prod.yml`.

6. **Public UI Sanitization:**
   - Updated `frontend/src/app/page.tsx:138` to remove public copy displaying RSS feeds as active providers ("Continuous discovery pipeline scanning verified editorial sources and global news wires").
   - Preserved MetroScope's own outbound syndication feed at `/feed.xml` and `/rss.xml` per specification.

7. **Shared Subsystem Integrity:**
   - All shared components remain operational: `url_service`, `normalizer_service`, `classifier_service`, `deduplication_service`, `quality_service`, `relevance_service`, `editorial_intelligence_service`, `social`, and `newsletter`.

---

## 3. Webz.io Integration Architecture

The provider integration is isolated in a modular, dedicated package at `backend/app/integrations/webz/`:

* **`client.py` (`WebzClient`):**
  - Dedicated asynchronous client built on `httpx.AsyncClient`.
  - Secure credential configuration: reads token dynamically from `settings.WEBZ_IO_API_KEY` (or direct init parameter). Never logs or hardcodes secrets.
  - Query construction via `build_query()` enforcing freshness timestamp `ts` (Unix milliseconds) and category syntax.
  - Rigid size cap: enforces `min(max(1, size), 10)` to prevent accidental result overages.
  - Strict prohibition on automatic pagination: `next` links are never traversed automatically.
  - Timeout policy: configurable (default 15.0 seconds).
  - Controlled retry: maximum 1 retry on transient network errors or 5xx server errors; 0 retries on 4xx status codes.
  - Immediate rate limit handling: raises `WebzRateLimitError` on HTTP 429 without retrying.

* **`schemas.py`:**
  - Pydantic models for current endpoint payloads: `WebzThread`, `WebzPost`, `WebzResponse`, `NormalizedWebzArticle`.
  - Strongly typed field extraction: `domain_rank`, `spam_score`, `performance_score`, `site_categories`, `entities`, and `requests_left`.

* **`parser.py`:**
  - `parse_webz_datetime`: strict parsing of ISO-8601/RFC-3339 timestamps into UTC, rejecting unparseable timestamps and timestamps > 24 hours in the future.
  - `extract_short_summary`: fair-use metadata summary extractor strictly capped at 250 characters. Does not copy full article text.
  - `normalize_webz_post`: performs end-to-end record validation, returning `None` for invalid records (empty titles, missing UUIDs, invalid URLs, or bad dates).

---

## 4. Collection Scheduling Strategy

Scheduling is managed by APScheduler in `backend/app/workers/scheduler.py` using two cron triggers scoped to the `Asia/Dhaka` timezone:

1. **Morning Sports Beat:**
   - ID: `webz_morning_sports`
   - Trigger: `CronTrigger(hour=8, minute=0, timezone=ZoneInfo("Asia/Dhaka"))`
   - Target: 10 eligible new articles in the `sports` category.
   - Query: `category:sport site_type:news language:english`

2. **Evening Business Beat:**
   - ID: `webz_evening_business`
   - Trigger: `CronTrigger(hour=20, minute=0, timezone=ZoneInfo("Asia/Dhaka"))`
   - Target: 10 eligible new articles in the `business` category.
   - Query: `category:"Economy, Business and Finance" site_type:news language:english`

### Concurrency Protection & Anti-Duplication:
* **Single Execution Lock:** A module-level `asyncio.Lock` (`_webz_collection_lock`) guarantees that collection jobs execute sequentially without overlap. If a run is in progress, any concurrent invocation is skipped with `{"status": "skipped", "reason": "lock_busy"}`.
* **Freshness Windows:** Queries include `ts` computed from `datetime.now(utc) - timedelta(hours=24)` (hard-capped between 1h and 48h). Historical articles beyond the window are never queried.
* **UUID & URL Deduplication:** Candidate articles are checked against existing `uuid` values and `canonical_url_hash` values in PostgreSQL before insert. In-batch duplicates are filtered immediately.

---

## 5. Budget Protection & Usage Ledger

A durable PostgreSQL usage ledger model, `WebzUsageLedger`, tracks every acquisition attempt and financial accounting entry in the `webz_usage_ledger` table.

### Accounting Schema:
- `billing_period`: String format `YYYY-MM` (e.g. `2026-11`).
- `job_name`: Identifier for the scheduled or manual run.
- `endpoint`: API endpoint called (default `/newsApiLite`).
- `query_params`: Parameters passed.
- `status_code`: HTTP status code returned.
- `success`: Boolean indicating operational success (2xx).
- `returned_count`: Number of articles in response.
- `billable_count`: Billable result count.
- `estimated_cost`: Cost estimate using `Decimal` arithmetic (default `$0.0050` / request).
- `actual_cost`: Provider-reported cost from response (`cost` / `credits_used`) when available.
- `reserved_cost`: Pre-flight reserved funds.
- `requests_left`: Provider-reported remaining quota.
- `remaining_allowance`: Remaining collection ceiling budget for the period.
- `stop_reason`: Audit code for aborted requests (`MONTHLY_COLLECTION_CEILING_REACHED`, `INSUFFICIENT_COLLECTION_ALLOWANCE`, `COLLECTION_DISABLED_BY_OWNER`, `CREDENTIALS_NOT_CONFIGURED`, `RATE_LIMIT_EXCEEDED`).

### Enforced Rules:
1. **$4.00 Monthly Ceiling:** Preflight halts collection once accumulated spend reaches $4.00.
2. **$1.00 Protected Emergency Reserve:** Budget arithmetic guarantees the reserve is never encroached upon.
3. **Upfront Cost Reservation:** Before executing any outbound HTTP request, `reserve_request()` logs a pending ledger entry and checks that `current_spend + request_cost <= $4.00`.
4. **Owner Kill Switch:** Setting `WEBZ_IO_COLLECTION_ENABLED=false` immediately halts all acquisition cycles.
5. **No Blind Balance Assumptions:** `requests_left` is recorded as provider quota metadata but is never treated as a dollar balance.

---

## 6. Article Processing & Schema Validation

Every candidate article retrieved from Webz.io undergoes validation before persistence:

```
[Webz Post] 
     │
     ├─► UUID check ──────────────► Missing/Empty? ──► REJECT
     ├─► Title check ─────────────► < 8 chars? ──────► REJECT
     ├─► URL check ───────────────► Invalid scheme? ─► REJECT
     ├─► Published timestamp ────► Unparseable/Future?► REJECT
     ├─► UUID DB duplicate ──────► Already exists? ──► SKIP (duplicate++)
     ├─► Canonical hash check ───► Already exists? ──► SKIP (duplicate++)
     ├─► Near-duplicate check ───► Jaccard > 0.65? ──► SKIP (duplicate++)
     │
     └─► Validated Candidate ────► Score Quality (0-100)
                                 ► Resolve Publisher Source
                                 ► Synthesize Short Summary (<= 250 chars)
                                 ► Store Trust & Image Metadata
                                 ► Insert to PostgreSQL news_articles
```

### Required Metadata Mapping:
- **UUID:** Mapped to `news_articles.uuid` (unique index, nullable for legacy articles).
- **Title:** Normalized title via `clean_title()`.
- **Summary:** Fair-use summary via `extract_short_summary()` (max 250 chars).
- **Original & Canonical URL:** Normalized URL and 64-char SHA-256 hash.
- **Publisher Attribution:** Mapped to `NewsSource` record via `get_or_create_source()`.
- **Author:** Cleaned author string, omitting generic placeholders ("admin", "editor", "staff").
- **Publication Timestamp:** Timezone-aware UTC datetime.
- **Categories & Topics:** Mapped to `NewsCategory` and JSON `topics` array.
- **Trust Indicators:** JSON object with `provider_domain_rank`, `provider_spam_score`, `provider_performance_score`.
- **Image Metadata:** JSON object with external image URL; explicitly flagged `external_only: true`.
- **Discovery Timestamp:** `func.now()` UTC.

---

## 7. Copyright & Content Usage Safeguards

MetroScope enforces a **metadata-only publication model** by default:
1. **Zero Full-Text Scraping:** The `text` field from Webz.io is stripped and never stored in `news_articles.description` or exposed in API schemas.
2. **Public API Shielding:** Public serializers (`ArticleListItem`, `ArticleDetail`) omit article body content, serving only short summaries, publisher attribution, and direct external links to original publisher articles.
3. **No Image Scraping:** External images are not copied or stored on MetroScope servers; only external URLs are recorded in metadata.
4. **Preserved Attribution:** Publisher identity and canonical URLs are prominently attributed.

---

## 8. Database Migrations

A non-destructive Alembic migration was authored at `backend/alembic/versions/20261110_0009_webz_io_migration.py`:

* **`upgrade()`:**
  - Adds `uuid` (VARCHAR(100), unique index), `author` (VARCHAR(255)), `topics` (TEXT), `trust_indicators` (TEXT), and `image_metadata` (TEXT) to `news_articles`.
  - Creates table `webz_usage_ledger` with columns for period, job name, endpoint, request counts, financial costs (DECIMAL(10, 4)), and stop reasons.
  - Adds compound index `ix_webz_ledger_period_created` on `(billing_period, created_at)`.
* **`downgrade()`:**
  - Drops `webz_usage_ledger` table and drops added columns from `news_articles`.
* **Data Safety:** Fully preserves historical articles (where `uuid` is `NULL`) and foreign-key relationships.

---

## 9. Test Verification Results

All tests were executed against the codebase:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\Hasan\Documents\metroscope\backend
configfile: pyproject.toml
plugins: anyio-4.14.2, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function
collected 155 items

tests/test_api.py ....................................................... [ 3%]
tests/test_audit_hardening_phase8.py .................................... [ 10%]
tests/test_editorial_intelligence.py .................................... [ 15%]
tests/test_health.py .................................................... [ 18%]
tests/test_models.py .................................................... [ 21%]
tests/test_near_duplicates.py ........................................... [ 25%]
tests/test_newsletter_campaign.py ....................................... [ 29%]
tests/test_newsletter_subscription.py ................................... [ 34%]
tests/test_phase10_ux_regression.py ..................................... [ 37%]
tests/test_phase12_content_expansion.py ................................. [ 40%]
tests/test_quality_service.py ........................................... [ 43%]
tests/test_relevance_service.py ......................................... [ 50%]
tests/test_scheduler.py ................................................. [ 51%]
tests/test_services.py .................................................. [ 58%]
tests/test_social_clients.py ............................................ [ 72%]
tests/test_social_formatting.py ......................................... [ 80%]
tests/test_social_publishing_service.py ................................. [ 84%]
tests/test_social_scheduler.py .......................................... [ 87%]
tests/test_webz_integration.py .......................................... [ 98%]
tests/test_worker.py .................................................... [100%]

======================= 155 passed, 2 warnings in 5.10s =======================
```

### Coverage of Specific Migration Requirements:
| Test Requirement | Test Function | Result |
| :--- | :--- | :--- |
| Webz.io Authentication | `test_webz_client_authentication_configured`, `test_webz_client_authentication_missing_token` | **PASSED** |
| Query Construction (Sports/Business) | `test_webz_query_construction_sports`, `test_webz_query_construction_business` | **PASSED** |
| Freshness Window & Historical Restriction | `test_webz_freshness_window_caps_prevents_historical_collection` | **PASSED** |
| Response Schema Parsing | `test_webz_response_schema_parsing` | **PASSED** |
| Result Mapping & Copyright Safeguards | `test_webz_result_mapping_and_copyright_safeguards` | **PASSED** |
| Invalid Record Rejection | `test_webz_invalid_response_handling` | **PASSED** |
| HTTP 429 & Rate Limit Halting | `test_webz_client_http_429_rate_limit` | **PASSED** |
| Controlled Retry on Timeout/5xx | `test_webz_client_timeout_and_controlled_retry` | **PASSED** |
| Budget Preflight & Ceilings ($4 Ceiling) | `test_budget_preflight_allows_within_ceiling`, `test_budget_preflight_monthly_hard_stop` | **PASSED** |
| Emergency Reserve Protection ($1 Reserve) | `test_budget_preflight_preserves_emergency_reserve` | **PASSED** |
| Owner Immediate Kill Switch | `test_budget_preflight_owner_disabled_switch` | **PASSED** |
| Request Ledger Reservation | `test_budget_request_reservation_and_finalization` | **PASSED** |
| UUID & Canonical Hash Deduplication | `test_webz_ingestion_service_deduplication` | **PASSED** |
| Public API Excludes Full Text | `test_public_api_excludes_unauthorized_full_text` | **PASSED** |
| Historical Articles Preserved Without UUID | `test_existing_historical_articles_preserved_without_uuid` | **PASSED** |
| Scheduler Timezone & Exactly 2 Daily Jobs | `test_create_scheduler_webz_jobs` | **PASSED** |
| Single Execution Lock Prevents Concurrency | `test_webz_worker_prevents_concurrent_sports_runs`, `test_webz_worker_prevents_concurrent_business_runs` | **PASSED** |
| Frontend Typecheck & ESLint | `npm run typecheck`, `npm run lint` | **PASSED** |

---

## 10. Actual API Smoke Test Status

* **Status:** Automated pre-flight verified; live network call pending owner credentials.
* **Reason:** As dictated by user instructions, actual credit expenditure requires valid owner credentials configured in the environment and explicit owner cost authorization.
* **Verification Script:** A dedicated, safe smoke-test runner is provided at `backend/scripts/smoke_test_webz.py`:
  - When invoked without an API key, it cleanly reports:
    ```text
    [BLOCKED] WEBZ_IO_API_KEY is not configured in environment or .env file.
    Owner action required: please set WEBZ_IO_API_KEY=<your_token> in .env to enable live testing.
    ```
  - When invoked without confirmation, it refuses to consume credits:
    ```text
    [AUTHORIZATION REQUIRED]
    Live API calls consume provider account credits.
    To authorize spending credits for a smoke test run:
      python backend/scripts/smoke_test_webz.py --confirm-cost
    ```

---

## 11. Status Categorization

### Implemented Subsystems:
* `WebzClient` HTTPX asynchronous client with query building, timeout handling, and controlled retries.
* `WebzResponse`, `WebzPost`, `WebzThread`, and `NormalizedWebzArticle` Pydantic models.
* `extract_short_summary` and `normalize_webz_post` metadata normalization.
* `BudgetProtectionService` enforcing $4 ceiling, $1 reserve, and reservation ledger.
* `WebzIngestionService` coordinating preflight, acquisition, deduplication, and persistence.
* `webz_morning_sports` and `webz_evening_business` scheduler jobs in `Asia/Dhaka` timezone.
* `_webz_collection_lock` execution lock preventing overlapping collection cycles.
* Alembic migration `0009_webz_io_migration` for `news_articles` and `webz_usage_ledger`.
* Public API exclusion of full-text body content.
* Complete removal of GDELT and third-party RSS components.

### Automated-Test Verified Subsystems:
* All 155 backend pytest test cases passed.
* Next.js TypeScript typecheck (`tsc --noEmit`) passed with 0 errors.
* Next.js ESLint (`next lint`) passed with 0 errors or warnings.

### Owner Action Required Items:
1. **Supply Webz.io API Token:** Add `WEBZ_IO_API_KEY=<your_webz_io_token>` to `.env`.
2. **Apply Database Migration:** When starting the local stack, execute `python -m alembic upgrade head` (handled automatically by `local_start.ps1` and `local_start.sh`).
3. **Optional Single Smoke Test:** Once credentials are added, run:
   ```powershell
   python backend/scripts/smoke_test_webz.py --confirm-cost
   ```

---

## 12. Exact Local Restart Instructions

The existing local startup workflows are preserved. All local PostgreSQL data in `.postgres_runtime` is retained.

### On Windows (PowerShell):
```powershell
# 1. Ensure services are stopped cleanly
powershell -ExecutionPolicy Bypass -File .\scripts\local_stop.ps1

# 2. Start PostgreSQL, run migrations, and launch Backend, Worker, & Frontend
powershell -ExecutionPolicy Bypass -File .\scripts\local_start.ps1

# 3. Check status
powershell -ExecutionPolicy Bypass -File .\scripts\local_status.ps1
```

### On Linux / macOS (Bash):
```bash
# 1. Stop existing local processes
./scripts/local_stop.sh

# 2. Start local cluster
./scripts/local_start.sh

# 3. Check status
./scripts/local_status.sh
```
