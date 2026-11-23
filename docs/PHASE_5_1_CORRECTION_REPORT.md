# METROSCOPE — PHASE 5.1 CORRECTION REPORT
## Production Reliability, API Compliance & Recovery Corrections

**Engineer:** Principal Backend Engineer, Senior Python Developer, API Integration Specialist, PostgreSQL Reliability Engineer, and DevOps Engineer  
**Date:** 2026-11-07  
**Status:** **PASS — PHASE 5.1 CORRECTIONS COMPLETE**  
**Audit Reference:** [`docs/PHASE_5_INDEPENDENT_TECHNICAL_AUDIT.md`](file:///c:/Users/Hasan/Documents/metroscope/docs/PHASE_5_INDEPENDENT_TECHNICAL_AUDIT.md)

---

## 1. Executive Summary

Phase 5.1 resolves all four findings (M-01, M-02, L-01, L-02) and addresses the informational finding identified during the Phase 5 independent technical verification audit.

The corrections harden the social publishing subsystem against malformed upstream HTTP responses, implement official Twitter Text v3 character and URL weighting, provide a conservative recovery mechanism for stale in-flight publication records with strict duplicate prevention, make Docker Compose environment variable injection explicit, and introduce rolling 24-hour quota management for X and Facebook.

### Summary of Verification Results
- **Backend Test Suite:** **106/106 passed** in 2.63s (18 new regression tests added, 0 failures, 1 deprecation warning from Starlette).
- **Frontend Quality Assurance:** `npm run typecheck` (`tsc --noEmit`) and `npm run lint` (`next lint`) both passed with **0 errors and 0 warnings**; `npm run build` compiled all 12 routes cleanly.
- **Database & Alembic:** Applied Alembic migration `0007_stale_recovery` on live PostgreSQL (Port 5433); confirmed linear revision history, safe upgrade and downgrade, column length expansion (`VARCHAR(32)`), and new recovery columns (`recovered_at`, `recovery_notes`).
- **Infrastructure:** `docker compose config` confirmed explicit forwarding of all social publishing variables and limits within the approved 1,408 MB container memory boundary on AWS EC2 `t3.small`.
- **Failure Injection Suite:** All 14 isolated failure modes re-verified, confirming zero unhandled `JSONDecodeError` escapes on malformed HTTP 200/201 responses.

---

## 2. Detailed Findings & Resolutions

### Finding 1: M-01 — Safe JSON Response Parsing
- **Severity:** MEDIUM
- **Affected Files:**
  - [`backend/app/social/base.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/social/base.py)
  - [`backend/app/social/facebook_client.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/social/facebook_client.py)
  - [`backend/app/social/x_client.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/social/x_client.py)
  - [`backend/tests/test_social_clients.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/tests/test_social_clients.py)
- **Root Cause:** Both `FacebookPageClient` and `XClient` directly called `response.json()` upon receiving HTTP 200/201 status codes without guarding against `json.JSONDecodeError` or non-dictionary JSON payloads. Upstream gateways, proxies, or CDNs returning HTML error pages with HTTP 200/201 caused unhandled exceptions escaping the client. Furthermore, blind retries on malformed HTTP 200/201 risked creating duplicate posts if the platform had already created the post.
- **Resolution:**
  1. Created `safe_parse_json_response(response_text, status_code, provider)` in `base.py`:
     - Checks for empty response bodies and returns structured diagnostic error.
     - Decodes JSON inside `try ... except Exception`, converting parsing failures into clean diagnostic strings with safe text previews.
     - Validates that decoded data is a JSON dictionary (`isinstance(data, dict)`).
     - Never logs or exposes raw Authorization headers or secrets.
  2. In `FacebookPageClient`:
     - Validates `post_id = data.get("id")`. If missing or if JSON is malformed on HTTP 200, marks outcome as unknown and **aborts retries** to prevent duplicate publishing.
     - Safely parses error responses; falls back to sanitized text previews on non-JSON error bodies.
  3. In `XClient`:
     - Validates `data.get("data", {}).get("id")`. If missing or malformed on HTTP 201, marks outcome as unknown and **aborts retries**.
     - Safely parses X API v2 error envelopes (`detail`, `title`, `errors`); falls back to sanitized text previews.

---

### Finding 2: M-02 — X Official URL and Character Weighting Validation
- **Severity:** MEDIUM
- **Affected Files:**
  - [`backend/app/social/content_formatter.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/social/content_formatter.py)
  - [`backend/app/social/__init__.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/social/__init__.py)
  - [`backend/tests/test_social_formatting.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/tests/test_social_formatting.py)
- **Root Cause:** Content formatting relied on Python's built-in `len(text)` to enforce the 280-character limit. Under the official X (Twitter) Text v3 specification:
  - All URLs are wrapped by `t.co` and assigned a fixed weight of **23 characters**.
  - Measuring raw Python length over-penalized headlines for long MetroScope URLs ($> 23$ chars), while under-penalizing short URLs ($< 23$ chars), creating edge-case rejection risks.
- **Resolution:**
  1. Implemented `calculate_x_post_weighted_length(text: str) -> int` according to the official Twitter Text v3 configuration (`config/v3.json`):
     - Unicode NFC normalization (`unicodedata.normalize('NFC', text)`).
     - Standard URL regex extraction matching HTTP/HTTPS URLs. Every recognized URL contributes exactly **23 weighted characters** regardless of its raw length.
     - Character code points in official single-weight ranges (0..4351 covering Basic Latin, Latin-1, Greek, Cyrillic, Hebrew, Arabic, and Indic/Bangla scripts; 8192..8205; 8208..8223; 8242..8247) count as **1 weighted unit**.
     - All other characters (CJK, Emojis, supplementary symbols) count as **2 weighted units**.
  2. Updated `format_x_post`:
     - Computes the combined weighted length of `prefix + headline + suffix`.
     - Dynamically truncates headline characters from the end until the total post length satisfies `calculate_x_post_weighted_length(post) <= max_chars` (280).
  3. Updated `validate_x_post_length(text: str, max_chars: int = 280)` to use `calculate_x_post_weighted_length`.

---

### Finding 3: L-01 — Stale Publishing Record Recovery & Duplicate Prevention
- **Severity:** LOW
- **Affected Files:**
  - [`backend/app/models/social.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/social.py)
  - [`backend/alembic/versions/20261107_0007_stale_recovery.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/alembic/versions/20261107_0007_stale_recovery.py)
  - [`backend/app/repositories/social_repository.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/repositories/social_repository.py)
  - [`backend/app/social/publishing_service.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/social/publishing_service.py)
  - [`backend/app/social/publishing_scheduler.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/social/publishing_scheduler.py)
  - [`backend/app/workers/scheduler.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/workers/scheduler.py)
  - [`backend/tests/test_social_publishing_service.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/tests/test_social_publishing_service.py)
  - [`backend/tests/test_social_scheduler.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/tests/test_social_scheduler.py)
- **Root Cause:** If a worker process crashed or the container restarted while an article was in `status="PUBLISHING"`, the record remained in `PUBLISHING` indefinitely. Because `get_eligible_articles_for_social` filtered out both `PUBLISHED` and `PUBLISHING`, that article was permanently skipped. Automatically retrying stale `PUBLISHING` records, however, risks duplicate posting if the external API call had actually succeeded before the crash.
- **Resolution:**
  1. **Database Migration `0007_stale_recovery`:**
     - Expanded `status` column on `social_posts` from `VARCHAR(20)` to `VARCHAR(32)` to accommodate `FAILED_AMBIGUOUS` and `RECONCILIATION_REQUIRED`.
     - Added `recovered_at` (`TIMESTAMPTZ`, nullable) and `recovery_notes` (`TEXT`, nullable).
     - Added composite index `ix_social_posts_status_updated_at` on `(status, updated_at)`.
  2. **Conservative Ambiguous Recovery Policy:**
     - Query `get_stale_publishing_posts` retrieves records where `status = 'PUBLISHING'` and `updated_at <= NOW() - 60 minutes`.
     - Uses PostgreSQL `with_for_update(skip_locked=True)` to prevent concurrent recovery jobs from racing.
     - Transitions stale records to `status = 'FAILED_AMBIGUOUS'`, records `recovered_at = NOW()`, and sets diagnostic `recovery_notes` indicating manual reconciliation is required.
     - In `get_eligible_articles_for_social`, `published_subq` excludes articles with status in `["PUBLISHED", "PUBLISHING", "FAILED_AMBIGUOUS", "RECONCILIATION_REQUIRED"]`. This guarantees **zero automatic duplicate publishing**.
  3. **Scheduler Integration:**
     - Registered standalone APScheduler job `social_stale_recovery` (running every 60 minutes) guarded by `_social_recovery_lock`.
     - Also executed at the start of each publishing cycle in `SocialPublishingService.run_publishing_cycle`.

---

### Finding 4: L-02 — Explicit Social Environment Configuration
- **Severity:** LOW
- **Affected Files:**
  - [`docker-compose.yml`](file:///c:/Users/Hasan/Documents/metroscope/docker-compose.yml)
  - [`backend/app/core/config.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/core/config.py)
  - [`.env.example`](file:///c:/Users/Hasan/Documents/metroscope/.env.example)
- **Root Cause:** In `docker-compose.yml`, the `worker` service did not explicitly declare the social publishing environment variables, relying implicitly on local `.env` container mounts.
- **Resolution:**
  1. Updated `docker-compose.yml` `services.worker.environment` to explicitly declare all social configuration settings with secure shell variable expansions and default fallbacks:
     - `SITE_URL: ${SITE_URL:-https://metroscope.news}`
     - `SOCIAL_PUBLISHING_ENABLED: ${SOCIAL_PUBLISHING_ENABLED:-false}`
     - `SOCIAL_DRY_RUN: ${SOCIAL_DRY_RUN:-true}`
     - `SOCIAL_PUBLISHING_INTERVAL_MINUTES: ${SOCIAL_PUBLISHING_INTERVAL_MINUTES:-30}`
     - `SOCIAL_MAX_POSTS_PER_RUN: ${SOCIAL_MAX_POSTS_PER_RUN:-2}`
     - `SOCIAL_MIN_QUALITY_SCORE: ${SOCIAL_MIN_QUALITY_SCORE:-70.0}`
     - `STALE_PUBLISHING_TIMEOUT_MINUTES: ${STALE_PUBLISHING_TIMEOUT_MINUTES:-60}`
     - `FACEBOOK_ENABLED: ${FACEBOOK_ENABLED:-false}`
     - `FACEBOOK_PAGE_ID: ${FACEBOOK_PAGE_ID:-}`
     - `FACEBOOK_PAGE_ACCESS_TOKEN: ${FACEBOOK_PAGE_ACCESS_TOKEN:-}`
     - `FACEBOOK_API_VERSION: ${FACEBOOK_API_VERSION:-v21.0}`
     - `FACEBOOK_MAX_POSTS_PER_DAY: ${FACEBOOK_MAX_POSTS_PER_DAY:-48}`
     - `X_ENABLED: ${X_ENABLED:-false}`
     - `X_API_KEY: ${X_API_KEY:-}`
     - `X_API_SECRET: ${X_API_SECRET:-}`
     - `X_ACCESS_TOKEN: ${X_ACCESS_TOKEN:-}`
     - `X_ACCESS_TOKEN_SECRET: ${X_ACCESS_TOKEN_SECRET:-}`
     - `X_BEARER_TOKEN: ${X_BEARER_TOKEN:-}`
     - `X_MAX_POSTS_PER_DAY: ${X_MAX_POSTS_PER_DAY:-15}`
  2. Updated `.env.example` with clear placeholders and documentation for all new settings.
  3. Confirmed with `docker compose config`.

---

### Finding 5: Informational — X API Rolling 24-Hour Quota Management
- **Severity:** INFORMATIONAL
- **Affected Files:**
  - [`backend/app/core/config.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/core/config.py)
  - [`backend/app/repositories/social_repository.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/repositories/social_repository.py)
  - [`backend/app/social/publishing_service.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/social/publishing_service.py)
  - [`backend/tests/test_social_publishing_service.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/tests/test_social_publishing_service.py)
- **Root Cause:** A 30-minute interval with up to 2 posts per run could produce 96 posts/day, which exceeds the X API Free tier quota of 17 posts per 24 hours.
- **Resolution:**
  1. Added `X_MAX_POSTS_PER_DAY: int = 15` (default conservative cap, customizable via `.env` for Basic/Pro tiers).
  2. Added `FACEBOOK_MAX_POSTS_PER_DAY: int = 48`.
  3. Added `get_published_count_in_window(db, platform, window_hours=24)` in `social_repository.py` to calculate exact published posts in the rolling 24-hour window using PostgreSQL timestamps.
  4. In `SocialPublishingService._publish_to_platform`:
     - Checks published count in the last 24 hours against the daily cap.
     - If cap is reached, skips run with a logged warning (`stats["skipped_quota"] = 1`).
     - If remaining budget is less than `max_posts_per_run`, dynamically throttles `effective_limit` to `remaining_today`.

---

## 3. Test Execution & Evidence

### 3.1 Backend Test Suite (Pytest)
```
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\Hasan\Documents\metroscope\backend
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.14.2, asyncio-1.4.0
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=function, asyncio_default_test_loop_scope=function
collected 106 items

tests\test_api.py ......                                                 [  5%]
tests\test_editorial_intelligence.py ........                            [ 13%]
tests\test_gdelt_client.py ...                                           [ 16%]
tests\test_health.py ..                                                  [ 17%]
tests\test_ingestion.py ...                                              [ 20%]
tests\test_models.py .....                                               [ 25%]
tests\test_near_duplicates.py ......                                     [ 31%]
tests\test_quality_service.py ....                                       [ 34%]
tests\test_relevance_service.py ............                             [ 46%]
tests\test_scheduler.py .                                                [ 47%]
tests\test_services.py ..........                                        [ 56%]
tests\test_social_clients.py ......................                      [ 77%]
tests\test_social_formatting.py ............                             [ 88%]
tests\test_social_publishing_service.py .......                          [ 95%]
tests\test_social_scheduler.py ....                                      [ 99%]
tests\test_worker.py .                                                   [100%]

======================= 106 passed, 1 warning in 2.63s ========================
```

### 3.2 Frontend Verification
```
> metroscope-frontend@0.1.0 typecheck
> tsc --noEmit (0 errors)

> metroscope-frontend@0.1.0 lint
> next lint (0 warnings or errors)

> metroscope-frontend@0.1.0 build
> next build (12/12 static/dynamic routes compiled cleanly)
```

### 3.3 Failure-Injection Verification
The 14 isolated failure injection scenarios were executed against the corrected codebase:
1. Facebook Timeout: **PASS** (Network error handled cleanly).
2. X Timeout: **PASS** (Network error handled cleanly).
3. HTTP 429 Rate Limit: **PASS** (Rate limit logged; retried safely).
4. HTTP 500 Server Error: **PASS** (Logged and marked FAILED).
5. Invalid Access Token: **PASS** (Non-retryable code 190 aborts futile retries).
6. Missing Credentials: **PASS** (Aborts before network dispatch; configuration logged).
7. Malformed API Response: **PASS** (Unhandled JSONDecodeError: **False**; captured as unknown outcome, aborting retries).
8. DB Failure After API Success: **PASS** (Transaction rolled back; exception logged).
9. Worker Restart / Stale Record: **PASS** (Interrupted record transitioned to FAILED_AMBIGUOUS; duplicate prevented).
10. Duplicate Scheduler Overlap: **PASS** (In-process lock prevented overlap).
11. Concurrent DB Insertion: **PASS** (Database UNIQUE constraint prevented duplicate).
12. Invalid Article Data: **PASS** (Empty text rejected prior to network call).
13. X Character Limit Overflow: **PASS** (Weighted 280-char guard rejected overflow).
14. Dry-Run Mode: **PASS** (Simulated post IDs generated; zero outbound HTTP calls).

---

## 4. Known Limitations & Production Readiness Checklist

1. **Live Social Credentials:**  
   Live publishing remains in safe dry-run mode (`SOCIAL_DRY_RUN=true`). To activate live publishing in production:
   - Provide Meta Page ID and Page Access Token with `pages_manage_posts` and `pages_read_engagement` permissions.
   - Provide X API v2 credentials (`X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`).
   - Set `SOCIAL_DRY_RUN=false` and `SOCIAL_PUBLISHING_ENABLED=true` in `.env`.
2. **Ambiguous Stale Record Reconciliation:**  
   If an unexpected worker crash leaves records in `FAILED_AMBIGUOUS`, an operator should verify the Facebook Page or X account feed before manually updating the record status to `FAILED` or `PUBLISHED`.

---

## 5. Final Implementation Verdict

```
================================================================================
FINAL VERDICT: PASS — PHASE 5.1 CORRECTIONS COMPLETE
================================================================================
```
All Phase 5 audit findings have been resolved, fully tested with 106 automated tests, and verified on live PostgreSQL and Next.js production builds.
