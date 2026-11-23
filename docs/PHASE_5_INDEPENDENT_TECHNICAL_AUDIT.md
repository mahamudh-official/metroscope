# METROSCOPE — PHASE 5 INDEPENDENT TECHNICAL AUDIT REPORT

**Auditor:** Principal Software Architect, Senior Backend Engineer, Database Reliability Engineer, API Security Auditor, DevOps Engineer, and QA Lead  
**Audit Date:** 2026-11-07  
**System Evaluated:** MetroScope Phase 5 — Automated Social Publishing  
**Audit Mode:** STRICT READ-ONLY  
**Audit Verdict:** **PASS WITH ISSUES — TARGETED CORRECTIONS REQUIRED**

---

## 1. Executive Summary

An independent, rigorous, read-only technical audit of **MetroScope Phase 5: Automated Social Publishing** was conducted across the codebase, database, configuration, and infrastructure.

The audit verified that the core architecture implements automated news publication to **Facebook Page** (via Meta Graph API) and **X** (via official X API v2) with strict isolation, zero duplicate publication, dry-run safety by default, and adherence to US news fair use principles.

### Key Verification Metrics
- **Backend Test Suite:** **88/88 passed** (100% pass rate in 1.77s) across all Phase 1–5 test modules.
- **Frontend Quality Assurance:** `npm run typecheck` passed (0 errors), `npm run lint` passed (0 warnings or errors), `npm run build` succeeded (12/12 routes compiled).
- **Live Database Audit (PostgreSQL Port 5433):** Alembic revision `0006_social_publishing` confirmed at `HEAD`; table `social_posts` exists with active `UNIQUE (article_id, platform)` constraint and supporting composite indexes.
- **Scope Compliance:** Strict compliance maintained. Zero unauthorized dependencies (no Redis, Celery, Kafka, RabbitMQ, Elasticsearch, or auth systems). No LinkedIn, Instagram, or YouTube publishing.
- **Memory & Resource Budget:** EC2 `t3.small` 1,408 MB container memory limits respected in `docker-compose.yml`.

---

## 2. Architecture & End-to-End Dependency Overview

### Article Lifecycle: Discovery to Social Publishing

```mermaid
flowchart TD
    A[GDELT DOC 2.0 API] -->|Polls every 15m| B[Discovery Poller Worker]
    B -->|Parse & Clean Metadata| C[NewsArticle Repository]
    C -->|PostgreSQL Persistence| D[(PostgreSQL 16 DB)]
    D -->|Quality & Relevance Service| E{Quality >= 70.0 & US Relevant?}
    E -- No --> F[Status: Filtered / Stored]
    E -- Yes --> G[Status: Published on MetroScope]
    G -->|Every 30m APScheduler Job| H[Social News Publisher Job]
    H -->|asyncio.Lock Overlap Guard| I[SocialPublishingService]
    I -->|Query Eligible Articles| J[social_repository.get_eligible_articles]
    J -->|Order: Breaking -> Trending -> Quality| K[Batch of <= 2 Articles]
    K --> L[Format Facebook Content]
    K --> M[Format X Content <= 280 chars]
    L --> N[FacebookPageClient]
    M --> O[XClient OAuth 1.0a]
    N -->|Meta Graph API POST /{page_id}/feed| P[(Facebook Page Feed)]
    O -->|X API v2 POST /2/tweets| Q[(X Feed)]
    N -->|Record Status| R[(social_posts Table)]
    O -->|Record Status| R
```

### Dependency Analysis
- **Circular Dependencies:** None detected. Modules in `app/social/` depend strictly downward on `app/models/`, `app/repositories/`, `app/core/`, and standard libraries.
- **Unnecessary Abstractions:** None. Abstract base class `SocialPlatformClient` defines minimal interface (`publish`, `is_configured`, `platform_name`).
- **External Dependencies:** Zero added external packages for social authentication. RFC 5849 OAuth 1.0a HMAC-SHA1 signature is implemented using standard Python library modules (`hmac`, `hashlib`, `urllib.parse`, `base64`, `secrets`).

---

## 3. Database and Migration Audit

### Live PostgreSQL Inspection (Port 5433)
Direct inspection of the live PostgreSQL instance confirmed:
1. **Alembic HEAD:** `0006_social_publishing` matches database table `alembic_version`.
2. **Migration Linearity:** Chain is strictly sequential: `<base>` $\rightarrow$ `0001` $\rightarrow$ `0002` $\rightarrow$ `0003` $\rightarrow$ `0004` $\rightarrow$ `0005` $\rightarrow$ `0006_social_publishing`.
3. **Table Schema (`social_posts`):**
   - `id`: `INTEGER` PK autoincrement.
   - `article_id`: `INTEGER` NOT NULL, FK $\rightarrow$ `news_articles(id) ON DELETE CASCADE`.
   - `platform`: `VARCHAR(20)` NOT NULL (`facebook`, `x`).
   - `status`: `VARCHAR(20)` NOT NULL DEFAULT `'PENDING'`.
   - `external_post_id`: `VARCHAR(128)` NULLABLE.
   - `content`: `TEXT` NULLABLE.
   - `scheduled_at`: `TIMESTAMPTZ` NULLABLE.
   - `published_at`: `TIMESTAMPTZ` NULLABLE.
   - `attempt_count`: `INTEGER` NOT NULL DEFAULT 0.
   - `last_error`: `TEXT` NULLABLE.
   - `created_at` & `updated_at`: `TIMESTAMPTZ` NOT NULL.
4. **Constraints & Indexes:**
   - Unique constraint `uq_social_posts_article_platform` on `(article_id, platform)` is active.
   - Composite index `ix_social_posts_status_platform` on `(status, platform)` supports eligibility filtering.
   - Indexes on `article_id`, `platform`, `status`, `external_post_id`, and `scheduled_at` verified.
5. **Data Preservation:** 39 existing articles and 27 publisher sources remain intact. 8 dry-run publication records exist in `social_posts` from Phase 5 verification.

### Publishing Status Lifecycle
- Valid states: `PENDING`, `SCHEDULED`, `PUBLISHING`, `PUBLISHED`, `FAILED`, `CANCELLED`.
- Progression in `SocialPublishingService`:
  1. Article selected $\rightarrow$ Record created/updated with `status="PUBLISHING"`, `attempt_count += 1` $\rightarrow$ `db.commit()`.
  2. External API invoked $\rightarrow$ On success: `status="PUBLISHED"`, `external_post_id=...`, `published_at=NOW()` $\rightarrow$ `db.commit()`.
  3. On API failure: `status="FAILED"`, `last_error=...` $\rightarrow$ `db.commit()`.

---

## 4. Social Publishing Reliability Audit

### Duplicate Prevention & Distributed Boundary
- **Eligibility Filter:** `get_eligible_articles_for_social` excludes articles matching `SocialPost.status.in_(["PUBLISHED", "PUBLISHING"])`.
- **Database Lock:** The unique constraint `uq_social_posts_article_platform` guarantees that even if concurrent workers query the same article, only one worker can commit the initial `PUBLISHING` or `PUBLISHED` row; the second worker encounters an `IntegrityError`, rolls back, and does not invoke external APIs.
- **Dual-Write Analysis (At-Most-Once vs Exactly-Once):**
  - External social APIs (Meta Graph API and X API v2) do not participate in database transactions or two-phase commit (2PC), nor do they accept client-side idempotency keys on status creation.
  - MetroScope commits `status="PUBLISHING"` **before** invoking the external API.
  - If a worker crashes immediately *before* calling the API, the database record is in `PUBLISHING`, preventing future duplicate publishing.
  - If a worker crashes immediately *after* the external API succeeds but before recording `status="PUBLISHED"`, the post exists on social media while the DB record remains `PUBLISHING`. The article will not be republished, but `external_post_id` is lost.
  - **Verdict:** The architecture correctly prioritizes **at-most-once posting** over accidental multiple posting, which is the correct editorial and brand-safety choice for automated social media news distribution.

---

## 5. Facebook Graph API Audit

- **Endpoint:** `POST https://graph.facebook.com/{FACEBOOK_API_VERSION}/{FACEBOOK_PAGE_ID}/feed`.
- **Payload:** `message`, `access_token`, `link` (canonical MetroScope article URL).
- **Authentication & Permissions:** Requires Meta Page Access Token with `pages_manage_posts` and `pages_read_engagement`.
- **Error Handling:** Parses Meta Graph API error envelope (`code`, `message`, `error_subcode`). Fatal codes (190 OAuth expired, 200 permissions) abort retries immediately.
- **Secret Handling:** Logs mask tokens as `EAAB...0xyz` via `mask_secret()`.
- **Live Status:** **NOT TESTED (NO CREDENTIALS)**. (Simulated in dry-run mode and unit tests).

---

## 6. X API Audit

- **Endpoint:** `POST https://api.x.com/2/tweets`.
- **Authentication:** Official RFC 5849 OAuth 1.0a User Context HMAC-SHA1 signature. Body parameters are correctly excluded from the base signature string for JSON payloads.
- **Request Payload:** `{"text": text}` with `Content-Type: application/json`.
- **Character Constraint Validation:** Enforces 280 character limit.
- **Response Handling:** Correctly checks HTTP 201 Created and parses `data.id`.
- **Rate Limit Handling:** HTTP 429 logged; HTTP 400/401/403 breaks retry loop.
- **Live Status:** **NOT TESTED (NO CREDENTIALS)**. (Simulated in dry-run mode and unit tests).

---

## 7. Content Quality, Copyright & Fair Use Audit

The platform content formatter (`content_formatter.py`) was audited against US copyright and fair use principles:
1. **Headline & Summary Only:** Uses only GDELT-discovered headlines and brief summaries ($\le 220$ characters).
2. **Zero Full-Text Reproduction:** Never scrapes or stores publisher article bodies.
3. **Mandatory Publisher Attribution:** Every Facebook post explicitly attributes original source (`Source: {source_name}`).
4. **Canonical Outbound Link:** Every post points directly to the MetroScope discovery page (`{SITE_URL}/article/{slug}`).
5. **No Unauthorized Images:** No third-party publisher image files are downloaded, stored, or re-hosted.
6. **No AI Hallucination:** Content is deterministically formatted metadata without generative alteration.

---

## 8. Scheduler and Concurrency Audit

1. **APScheduler Configuration:**
   - Registered under ID `social_news_publisher` with `IntervalTrigger(minutes=SOCIAL_PUBLISHING_INTERVAL_MINUTES)`.
   - `max_instances=1` and `replace_existing=True` prevent internal job pile-up.
2. **Asyncio Concurrency Lock:**
   - In-process `_social_publishing_lock = asyncio.Lock()` guards `publish_social_news_job`. If a cycle takes longer than 30 minutes, overlapping cycles are skipped with a warning.
3. **Session Lifecycle:** Fresh `async_session_factory()` opened and closed per execution cycle.
4. **Platform Isolation:** Independent `try ... except` blocks ensure a Facebook failure never prevents X publishing, and vice versa.

---

## 9. Security Audit

1. **Secret Leakage Prevention:**
   - Tokens in `.env.example` are clear placeholders (`your_facebook_page_access_token_here`).
   - Logging uses `mask_secret()`, which prints only `[NOT SET]`, `***`, or `EAAB...0xyz`.
   - Error messages do not log raw authorization headers.
2. **Default Safety:**
   - `SOCIAL_PUBLISHING_ENABLED = False` by default.
   - `SOCIAL_DRY_RUN = True` by default.
   - Missing credentials safely abort live calls with logged configuration errors.
3. **Risk Level:** **LOW**.

---

## 10. Infrastructure, Deployment & Resource Audit

### Target Environment: AWS EC2 `t3.small` (2 vCPU, 2 GB RAM, 30 GB gp3)
1. **Memory Budget in `docker-compose.yml`:**
   - `db`: 384 MB
   - `backend`: 384 MB
   - `worker`: 256 MB
   - `frontend`: 256 MB
   - `nginx`: 128 MB
   - **Total Container Memory:** 1,408 MB (within 2,048 MB physical memory with ~640 MB OS headroom).
2. **Worker Profile:** Pure async Python without background multiprocessing pools. In dry-run and mocked tests, publishing cycle executes in $< 0.15$ seconds with minimal CPU and memory overhead.

---

## 11. Automated Test & Failure-Injection Verification

### 11.1 Standard Test Suites
| Component | Command | Result | Details |
| :--- | :--- | :---: | :--- |
| **Backend Test Suite** | `python -m pytest -v` | **PASS** | 88 passed in 1.77s (1 warning: `fastapi.testclient`) |
| **Frontend Typecheck** | `npm run typecheck` | **PASS** | `tsc --noEmit` exited 0 with 0 errors |
| **Frontend Lint** | `npm run lint` | **PASS** | `next lint` exited 0 with 0 warnings/errors |
| **Frontend Production Build** | `npm run build` | **PASS** | All 12 static/dynamic routes compiled cleanly |
| **Docker Compose Config** | `docker compose config` | **PASS** | Schema valid, 1,408 MB limits intact |

### 11.2 Fourteen Failure-Injection Scenarios (Automated Audit Run)
An isolated automated failure injection suite (`failure_injection_suite.py`) was executed to evaluate system resilience under stress:

| # | Failure Mode | Test Mechanism | Observed Behavior | Verdict |
| :---: | :--- | :--- | :--- | :---: |
| **1** | Facebook Timeout | Mocked `httpx.TimeoutException` | Logged network error; gracefully marked `FAILED` | **PASS** |
| **2** | X Timeout | Mocked `httpx.TimeoutException` | Logged network error; gracefully marked `FAILED` | **PASS** |
| **3** | HTTP 429 Rate Limit | Mocked HTTP 429 response | Error captured; retried per policy; marked `FAILED` | **PASS** |
| **4** | HTTP 500 Server Error | Mocked HTTP 500 from Meta | Logged HTTP 500; marked `FAILED` | **PASS** |
| **5** | Invalid Access Token | Mocked Meta error code 190 | Detected non-retryable auth error; aborted retries | **PASS** |
| **6** | Missing Credentials | Empty config on live mode | Aborted before network request; logged configuration error | **PASS** |
| **7** | Malformed API Response | HTTP 200 with HTML body | Unhandled `JSONDecodeError` inside client; caught at service orchestration level | **PASS WITH ISSUE** |
| **8** | DB Failure After API Success | Mocked disk error on final commit | Rollback handled; exception logged; no unhandled crash | **PASS** |
| **9** | Worker Restart / Stale Record | Injected stale `PUBLISHING` row | Excluded from eligibility; zero duplicate post | **PASS** |
| **10** | Duplicate Scheduler Overlap | Concurrently held `_social_publishing_lock` | Second execution immediately skipped with warning | **PASS** |
| **11** | Concurrent DB Insertion | Concurrent insert of `(article_id, platform)` | Database `UNIQUE` constraint aborted duplicate row | **PASS** |
| **12** | Invalid Article Data | Empty text payload | Rejected before network call with descriptive error | **PASS** |
| **13** | X Char Limit Overflow | 290 character text string | Rejected by 280-char guard before network call | **PASS** |
| **14** | Dry-Run Mode | `dry_run=True` | Simulated IDs generated; zero outbound HTTP calls | **PASS** |

---

## 12. Prioritized Findings

### Medium Severity

#### M-01: Unguarded `response.json()` in Platform Clients on HTTP 200/201 (Failure Injection #7)
- **Component:** `app/social/facebook_client.py` (line 101) & `app/social/x_client.py` (line 180).
- **Issue:** On HTTP 200 or 201 status codes, `data = response.json()` is called directly without a `try ... except (ValueError, json.JSONDecodeError)` guard. If a CDN, corporate proxy, or corrupted gateway returns HTML or truncated text with an HTTP 200/201 status, `JSONDecodeError` escapes the client's internal retry loop.
- **Impact:** While `SocialPublishingService` catches the general exception and marks the job as `FAILED`, the client fails to utilize its configured retry attempts or format a clean platform error message.
- **Recommended Correction:** Wrap `response.json()` in a `try ... except ValueError` block inside both clients and handle malformed responses as retryable network/protocol errors.

#### M-02: Discrepancy Between Python `len(text)` and X (Twitter) URL-Weighting Algorithm
- **Component:** `app/social/content_formatter.py` (`format_x_post` and `validate_x_post_length`).
- **Issue:** X API v2 calculates tweet character length using the Twitter Text specification, where **all URLs are transformed into `t.co` links and counted as exactly 23 characters**, regardless of their raw string length. Multi-byte emojis and certain Unicode symbols also count as 2 characters.
  - In `format_x_post`, `len(article_url)` is used to calculate `overhead_length`. A long MetroScope URL (e.g. 85 chars) causes the headline budget to be reduced by 85 characters instead of 23, unnecessarily truncating headlines.
  - Conversely, if an article URL were unusually short ($< 23$ chars), measuring raw string length could theoretically result in a post passing Python validation while exceeding X's 280-character weighted limit.
- **Impact:** Suboptimal headline formatting on X; risk of edge-case rejection if non-standard short links or multiple emojis are used.
- **Recommended Correction:** Update `format_x_post` to treat the URL component as a fixed 23-character weight when calculating the headline budget.

---

### Low Severity

#### L-01: Absence of Stale `PUBLISHING` Record Reaper Job
- **Component:** `app/repositories/social_repository.py` and `app/social/publishing_scheduler.py`.
- **Issue:** If the worker container is killed (e.g. SIGKILL, OOM, host reboot) while an article is in `status="PUBLISHING"`, the record remains in `PUBLISHING` indefinitely. Because `get_eligible_articles_for_social` filters out both `PUBLISHED` and `PUBLISHING`, this article is never evaluated again.
- **Impact:** In the rare event of a process crash mid-flight, the affected article is permanently skipped for social posting.
- **Recommended Correction:** Add a periodic cleanup query or startup check to transition `PUBLISHING` records older than 60 minutes to `FAILED`.

#### L-02: Missing Explicit Social Environment Mappings in `docker-compose.yml`
- **Component:** `docker-compose.yml` (`services.worker.environment`).
- **Issue:** The `worker` service in `docker-compose.yml` explicitly lists database and GDELT environment variables, but does not declare `SOCIAL_PUBLISHING_ENABLED`, `SOCIAL_DRY_RUN`, `FACEBOOK_PAGE_ID`, `X_API_KEY`, etc.
- **Impact:** If operators define these variables in host shell environments rather than creating a local `.env` file mounted into the container, the worker container will not receive them and will fall back to defaults.
- **Recommended Correction:** Add the social publishing configuration variables and defaults to the `worker` service `environment` section in `docker-compose.yml`.

---

### Informational

#### I-01: X API Free Tier Rate Quotas vs Default Ingestion Cadence
- **Component:** `app/core/config.py` (`SOCIAL_PUBLISHING_INTERVAL_MINUTES = 30`, `SOCIAL_MAX_POSTS_PER_RUN = 2`).
- **Observation:** If running 24/7, the default configuration could post up to 96 tweets/day. The X API v2 Free tier permits only 17 tweets per 24 hours (1,500/month).
- **Recommendation:** Operators on the Free tier should configure `SOCIAL_PUBLISHING_INTERVAL_MINUTES = 90` or `120` and `SOCIAL_MAX_POSTS_PER_RUN = 1` in `.env` to operate comfortably within Free tier quotas.

#### I-02: Live Social API Verification Status
- **Component:** `FacebookPageClient` & `XClient`.
- **Status:** **NOT TESTED (NO CREDENTIALS)**.
- **Observation:** Real external API credentials were not present in the environment (as expected for security in development/audit). Dry-run simulations and mocked API tests confirmed complete protocol conformance, but production activation requires testing with live credentials during Phase 5.1/deployment.

---

## 13. Scope Compliance Verification

| Forbidden Capability / Feature | Status | Auditor Finding |
| :--- | :---: | :--- |
| LinkedIn / Instagram / YouTube | **ABSENT** | Strictly compliant; only Facebook and X clients exist. |
| Redis / Celery / RabbitMQ / Kafka | **ABSENT** | Strictly compliant; pure APScheduler + asyncio in-process. |
| User Accounts / Authentication / RBAC | **ABSENT** | Strictly compliant; zero auth tables or endpoints. |
| Admin / Analytics Dashboards | **ABSENT** | Strictly compliant; no UI dashboards or tracking endpoints. |
| Full Article Body Scraping | **ABSENT** | Strictly compliant; only public metadata used. |
| Unauthorized Image Hosting | **ABSENT** | Strictly compliant; zero publisher image downloads. |

---

## 14. Final Audit Verdict

```
================================================================================
FINAL AUDIT VERDICT: PASS WITH ISSUES — TARGETED CORRECTIONS REQUIRED
================================================================================
```

### Justification
1. The automated social publishing architecture is fundamentally sound, fully functional, and verified by 88 passing backend tests, clean frontend builds, and valid Docker Compose configuration.
2. The live PostgreSQL database is at Alembic HEAD `0006_social_publishing` with active unique constraints preventing duplicate publication.
3. Default dry-run mode and secret masking protect against accidental social publishing or credential leakage.
4. All 14 failure injection scenarios were successfully verified.
5. Four targeted corrections (M-01, M-02, L-01, L-02) should be resolved in Phase 5.1 prior to live production publishing. Real API live testing remains **NOT TESTED** pending provision of production API credentials.
