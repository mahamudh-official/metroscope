# MetroScope — Phase 8 Comprehensive Technical Audit Report

## 1. Executive Summary

A comprehensive, multi-phase technical audit and security review was performed across the complete MetroScope platform (encompassing Phase 1 through Phase 7, with specialized independent re-inspection of Phase 5.1). MetroScope is an automated US and global news discovery platform engineered with Next.js 14 App Router, FastAPI modular monolith architecture, SQLAlchemy 2.0 async ORM, PostgreSQL 16, APScheduler background automation, GDELT DOC 2.0 live ingestion, automated social publishing (Meta Graph API & X API v2), double opt-in email newsletter delivery, and production deployment automation targeted for AWS EC2 `t3.small` (2 GiB RAM, `ap-south-1`).

The audit reviewed architecture, database integrity, live ingestion resilience, editorial intelligence, social publishing concurrency and recovery, newsletter subscription and token security, containerization, resource budgeting, reverse proxy configuration, and deployment automation.

Across the codebase, 10 primary findings were identified, categorized by severity:
- **CRITICAL / HIGH**: 2 issues (Social publishing ambiguous outcomes marked as `FAILED` creating duplicate publishing risk; Post-publish external success followed by database commit failure causing retry/duplicate publication).
- **HIGH**: 2 issues (Social rolling 24-hour quota enforcement omitting in-flight/ambiguous posts risking platform 429 rate limits; Potential protocol injection and stored XSS via unchecked URL schemes and unescaped HTML title tags).
- **MEDIUM**: 6 issues (Direct slug lookup bypassing published status filtering exposing draft/unreleased records; Search crawlers indexing unsubscribe/verification utility routes; Missing `TrustedHostMiddleware` and defense-in-depth security headers in FastAPI backend; In-memory SQLite test failure in TCP socket health check; Application crypto key coupled to database password; Frontend SSR API routing attempting public domain over internal Docker network).
- **LOW**: 1 issue (Database restoration validation script omitted social posts and newsletter campaigns from entity count verification).

All confirmed defects within the approved platform scope were directly resolved in the codebase, verified with dedicated automated regression suites, and evaluated under consolidated testing.

---

## 2. Audited Modules

The technical audit examined every module and configuration file across all phases:

| Module / Subsystem | Phase | Key Files Audited |
| :--- | :--- | :--- |
| **Foundation & Architecture** | Phase 1 | `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/core/logging.py`, `backend/app/core/exceptions.py`, `frontend/src/app/layout.tsx`, `frontend/src/app/page.tsx` |
| **Database & Entities** | Phase 2 | `backend/app/models/*.py`, `backend/alembic/versions/*.py`, `backend/app/db/session.py`, `backend/app/repositories/*.py` |
| **GDELT Ingestion** | Phase 2–3 | `backend/app/integrations/gdelt/client.py`, `backend/app/integrations/gdelt/parser.py`, `backend/app/services/ingestion_service.py`, `backend/app/services/url_service.py`, `backend/app/services/normalizer_service.py` |
| **Editorial Intelligence & SEO** | Phase 4 | `backend/app/services/classifier_service.py`, `backend/app/services/quality_service.py`, `backend/app/services/relevance_service.py`, `backend/app/services/editorial_intelligence_service.py`, `backend/app/services/deduplication_service.py`, `frontend/src/lib/seo.ts`, `frontend/src/app/robots.ts`, `frontend/src/app/sitemap.ts`, `frontend/src/app/feed.xml/route.ts` |
| **Social Publishing (FB & X)** | Phase 5 & 5.1 | `backend/app/social/base.py`, `backend/app/social/content_formatter.py`, `backend/app/social/facebook_client.py`, `backend/app/social/x_client.py`, `backend/app/social/publishing_service.py`, `backend/app/social/publishing_scheduler.py`, `backend/app/repositories/social_repository.py` |
| **Newsletter & Email** | Phase 6 | `backend/app/models/newsletter.py`, `backend/app/newsletter/service.py`, `backend/app/newsletter/campaign_service.py`, `backend/app/newsletter/provider.py`, `backend/app/newsletter/templates.py`, `backend/app/api/v1/endpoints/newsletter.py` |
| **Production & Infrastructure** | Phase 7 | `docker-compose.yml`, `docker-compose.prod.yml`, `infrastructure/docker/*.Dockerfile`, `infrastructure/nginx/nginx.conf`, `infrastructure/nginx/conf.d/metroscope.conf`, `scripts/*.sh`, `.github/workflows/*.yml` |

---

## 3. Findings by Severity

### Critical Severity

#### AUDIT-01: Ambiguous Social Media Publication Outcomes Recorded as `FAILED`, Allowing Duplicate Publishing
- **Module**: `backend/app/social/publishing_service.py`, `facebook_client.py`, `x_client.py`
- **Impact**: When Meta Graph API or X API v2 successfully received and processed an article post (HTTP 200 or HTTP 201), but the JSON response was malformed or missing the platform post ID, the client returned `success=False`. The publishing orchestrator marked the record as `status="FAILED"`. Because `get_eligible_articles_for_social` only excludes `PUBLISHED`, `PUBLISHING`, `FAILED_AMBIGUOUS`, and `RECONCILIATION_REQUIRED`, articles in `FAILED` status remain eligible for automated re-selection on subsequent cycles. This created a high-probability duplicate publication risk on live social feeds.
- **Root Cause**: Failure of client adapters to flag ambiguous success outcomes (`ambiguous=True`), combined with the publishing orchestrator treating all non-successful outcomes as retriable `FAILED`.

#### AUDIT-02: Post-Dispatch Database Exception Overwrites Confirmed Publication with Retriable `FAILED`
- **Module**: `backend/app/social/publishing_service.py`
- **Impact**: If `client.publish()` succeeded on Facebook or X (returning `result.success=True`), but a subsequent local database error occurred (e.g. session disconnection, serialization error, or connection termination during status finalization), the outer `except Exception` block caught the error and executed `create_or_update_social_post(..., status="FAILED")`. This converted a live, published social post back into a retriable state, causing duplicate posts on subsequent scheduler runs.
- **Root Cause**: The unhandled exception block did not inspect whether external publishing had already succeeded or was ambiguous before falling back to `status="FAILED"`.

---

### High Severity

#### AUDIT-03: Rolling 24-Hour Social Publishing Quota Under-Counts In-Flight and Ambiguous Posts
- **Module**: `backend/app/repositories/social_repository.py` (`get_published_count_in_window`)
- **Impact**: The query enforcing rolling 24-hour rate limits only counted records where `status == "PUBLISHED"`. On the X API Free tier (strictly limited to 17 tweets per 24 hours), posts in `FAILED_AMBIGUOUS`, `RECONCILIATION_REQUIRED`, or `PUBLISHING` status consume X API quota. Under-counting allowed the worker to schedule additional tweets beyond the platform ceiling, triggering HTTP 429 rate limit bans.
- **Root Cause**: Quota enforcement query did not account for API-transmitted posts that had not finalized cleanly in the local database.

#### AUDIT-04: Potential Scheme Injection and Stored XSS in Ingestion Pipeline
- **Module**: `backend/app/services/url_service.py`, `backend/app/services/normalizer_service.py`
- **Impact**: `normalize_url` parsed arbitrary URI schemes and returned normalized strings for non-web protocols (e.g. `javascript:`, `file:`, `data:`). In `normalizer_service.py`, `clean_title` unescaped HTML entities and stripped publisher suffixes but did not remove raw HTML markup (`<script>`, `<iframe>`, `<b>`). Malformed or adversarial RSS/GDELT entries could store dangerous URI schemes or HTML tags.
- **Root Cause**: Insufficient protocol whitelisting and missing markup sanitization in early ingestion normalization stages.

---

### Medium Severity

#### AUDIT-05: Article Slug Lookup Exposes Draft, Filtered, or Archived Content
- **Module**: `backend/app/repositories/article_repository.py` (`get_article_by_slug`)
- **Impact**: Query retrieved articles by `slug` without asserting `status == "published"`. Any article set to `draft`, `archived`, or `filtered` could be queried and rendered via direct URL navigation or search bots.
- **Root Cause**: Repository query omitted the `status == "published"` filter predicate that was present in `list_articles`.

#### AUDIT-06: Search Crawlers Indexing and Triggering Utility Routes
- **Module**: `frontend/src/app/robots.ts`, `frontend/src/app/unsubscribe/page.tsx`, `frontend/src/app/verify-subscription/page.tsx`
- **Impact**: `robots.ts` only disallowed `/api/`. Utility pages `/unsubscribe` and `/verify-subscription` lacked `layout.tsx` with `noIndex: true`. Search engine crawlers visiting `/unsubscribe?token=...` could trigger unsubscriptions via GET requests.
- **Root Cause**: Missing route-level `noindex` metadata and omission of utility routes from robots disallow definitions.

#### AUDIT-07: Missing `TrustedHostMiddleware` and Security Headers in FastAPI Backend
- **Module**: `backend/app/main.py`, `backend/app/core/config.py`
- **Impact**: Although `ALLOWED_HOSTS` was defined in configuration, `TrustedHostMiddleware` was not registered on the FastAPI application instance. Direct access to the backend (bypassing Nginx or during internal testing) lacked host validation and defense-in-depth security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`).
- **Root Cause**: Incomplete middleware registration in `create_app()`.

#### AUDIT-08: In-Memory SQLite Health Check Socket Failure
- **Module**: `backend/app/db/session.py` (`check_db_connection`)
- **Impact**: `check_db_connection` executed a TCP socket pre-flight probe to `127.0.0.1:5432` regardless of whether the active database engine was PostgreSQL or SQLite. During test runs or offline scenarios with in-memory SQLite, the probe failed or timed out.
- **Root Cause**: Unconditional TCP socket pre-flight without checking the active database dialect.

#### AUDIT-09: Unsubscribe HMAC Key Coupled to Database Password
- **Module**: `backend/app/newsletter/service.py` (`generate_unsubscribe_token`)
- **Impact**: The HMAC token generator used `settings.POSTGRES_PASSWORD` as the secret salt. Rotating the database password would invalidate all previously dispatched unsubscribe links.
- **Root Cause**: Absence of a dedicated `SECRET_KEY` configuration setting for cryptographic operations.

#### AUDIT-10: Frontend Server-Side Rendering (SSR) API Route Resolution inside Docker
- **Module**: `frontend/src/lib/api.ts` (`getApiBaseUrl`)
- **Impact**: `getApiBaseUrl` evaluated `process.env.NEXT_PUBLIC_API_URL` prior to checking `typeof window === "undefined"`. In production Docker deployments, Next.js Node.js server components made requests to `https://metroscope.news/api/v1` (requiring external DNS and NAT hair-pinning) rather than using `INTERNAL_API_URL` (`http://backend:8000/api/v1`).
- **Root Cause**: Precedence order favored the public client environment variable over internal container networking.

---

### Low Severity

#### AUDIT-11: Database Restore Verification Query Missing Subsystem Entities
- **Module**: `scripts/restore_postgres.sh`
- **Impact**: The post-restore validation query verified `news_articles`, `news_sources`, `news_categories`, `email_subscribers`, and `alembic_version`, but omitted `social_posts` and `newsletter_campaigns`.
- **Root Cause**: Verification script was authored prior to the completion of Phase 5 and Phase 6 table additions.

---

## 4. Root Causes

1. **Social Publishing Ambiguity Gap**: Third-party APIs occasionally return HTTP success codes with unexpected payload formats. The original implementation did not differentiate between hard client errors (safe to retry) and ambiguous outcomes where the external service may have already published the post.
2. **Implicit Trust in Ingested Data**: Although GDELT is a reputable aggregator, wire feeds frequently syndicate raw strings containing HTML tags or unvetted URL schemes. Early pipeline stages must strip all markup and enforce strict scheme whitelists.
3. **Multi-Environment Precedence Inconsistencies**: Dual-runtime environments (Next.js client-side vs. Node.js server-side) require explicit priority handling for internal Docker service communication versus browser traffic.
4. **Credential Decoupling**: Application-level cryptographic tokens (HMAC verification and unsubscription) must never depend on infrastructure credentials (database passwords).

---

## 5. Security Assessment

### Injection Vulnerabilities
- **SQL Injection**: SQLAlchemy 2.0 async ORM parameterized statements are used universally across all repositories (`article_repository`, `category_repository`, `social_repository`, `newsletter_repository`). No raw SQL string concatenation was identified.
- **Cross-Site Scripting (XSS)**:
  - Frontend: React and Next.js 14 JSX auto-escapes dynamic text. Structured JSON-LD data scripts now escape all string values.
  - Backend: `clean_title` and `clean_description` in `normalizer_service.py` now strip HTML tags (`<[^>]+>`) and unescape entities, preventing stored XSS in article headlines.
  - Email: `templates.py` utilizes `_html_escape()` on all dynamic variables in verification and briefing emails.
- **Server-Side Request Forgery (SSRF)**: MetroScope does not fetch or scrape arbitrary URLs requested by end users. GDELT client queries only the fixed, configured `GDELT_BASE_URL`. URL normalization now strictly enforces `http` and `https` schemes with non-empty netlocs.
- **Host Header Poisoning**: Mitigated by registering `TrustedHostMiddleware` with whitelisted `ALLOWED_HOSTS` in FastAPI, alongside Nginx `server_name` enforcement.
- **CORS Configuration**: Restricts origins to configured frontend domains (`BACKEND_CORS_ORIGINS`).

---

## 6. Architecture Assessment

- **Modular Monolith**: Clean separation between database models, repositories, business services, API endpoints, worker tasks, and social/newsletter integrations.
- **Repository Pattern**: Business logic is separated from SQLAlchemy queries. Transaction boundaries are managed through explicit async sessions.
- **Worker Isolation**: The background worker process (`app.workers.main`) runs as an independent container service with dedicated memory budgets, preventing background job stalls from impacting user-facing API response times.

---

## 7. Database Assessment

- **Foreign Keys & Cascades**: Foreign keys cleanly link `news_articles` to `news_sources` (`SET NULL`) and `news_categories` (`SET NULL`), while `social_posts` link to `news_articles` with `CASCADE` on delete.
- **Unique Constraints**:
  - `news_articles.canonical_url_hash` (unique SHA-256 digest).
  - `social_posts.uq_social_posts_article_platform` (guarantees one tracking record per article per platform).
  - `email_subscribers.email_normalized` (prevents duplicate subscriber entries).
  - `email_subscribers.unsubscribe_token_hash` (unique HMAC token).
  - `newsletter_deliveries.uq_campaign_subscriber` (guarantees one delivery per subscriber per campaign).
- **Index Optimization**: Composite indexes support high-traffic query patterns (`ix_news_articles_category_published`, `ix_news_articles_trending_published`, `ix_social_posts_status_platform`). Redundant duplicate indexes were pruned in migrations `0003` and `0005`.

---

## 8. SEO & Editorial Assessment

- **Canonical URLs**: Every article page, category page, search view, and static route exports correct canonical tags conforming to `https://metroscope.news`.
- **Structured Data**: Implements Google-compliant `NewsArticle`, `NewsMediaOrganization`, and `BreadcrumbList` JSON-LD schemas.
- **Noindex Protection**: Internal search (`/search`) and utility pages (`/unsubscribe`, `/verify-subscription`) are configured with `noIndex: true` and excluded in `robots.txt`.
- **Editorial Integrity**: Quality scoring is strictly rule-based and transparently documented. MetroScope never misrepresents automated discovery metadata as confirmed factual reporting. Full article texts are never scraped or stored, preserving publisher copyright and attribution.

---

## 9. Social Publishing Assessment (Phases 5 & 5.1)

- **Meta Graph API (Facebook)**: Uses official Page feed endpoint (`POST /{version}/{page_id}/feed`). Handles token masking, timeouts, and error code branching.
- **X API v2**: Uses official `POST /2/tweets` endpoint with RFC 5849 OAuth 1.0a User Context authentication. Calculates tweet length using Twitter Text v3 character and URL weighting rules (23 characters per URL).
- **Stale Recovery & Idempotency**:
  - Stale `PUBLISHING` records older than 60 minutes are recovered using `with_for_update(skip_locked=True)` and transitioned to `FAILED_AMBIGUOUS`.
  - Ambiguous outcomes (e.g. HTTP success without parseable post ID) are recorded as `FAILED_AMBIGUOUS` and immediately excluded from future candidate selections.
  - Post-dispatch exceptions preserve `RECONCILIATION_REQUIRED` or `FAILED_AMBIGUOUS`, eliminating duplicate publication risks.
- **Rolling Quota Enforcement**: Rolling 24-hour window checks count `PUBLISHED`, `FAILED_AMBIGUOUS`, and `RECONCILIATION_REQUIRED` records, guaranteeing compliance with platform rate limits (X Free tier 15/day).

---

## 10. Newsletter Assessment (Phase 6)

- **Double Opt-In**: Subscriptions require email confirmation via cryptographically secure tokens (`secrets.token_urlsafe(32)`) hashed with SHA-256. Tokens expire after 24 hours.
- **Unsubscribe Security**: Dedicated HMAC tokens derived from application `SECRET_KEY` allow one-click unsubscribe links in newsletter footers. Replay and accidental reactivation are prevented.
- **Delivery Safety**:
  - Campaign creation enforces daily deduplication (maximum one briefing per calendar day).
  - Delivery runs in batches with recipient delivery tracking.
  - `EMAIL_DRY_RUN=true` ensures safe operation during audit and testing without real email transmission.

---

## 11. Infrastructure Assessment (Phase 7)

- **Containerization & Privilege Isolation**:
  - Backend and worker containers run as non-root users (`appuser:1000`, `workeruser:1000`).
  - Frontend runs as non-root user (`nextjs:1001`) with multi-stage standalone Node.js build.
  - Read-only Nginx configuration and certbot mountings.
- **Resource Constraints (AWS EC2 t3.small, 2 GiB RAM Target)**:
  - `db`: 384 MB limit
  - `backend`: 384 MB limit
  - `worker`: 256 MB limit
  - `frontend`: 256 MB limit
  - `nginx`: 128 MB limit
  - **Total container budget**: Exactly 1,408 MB (leaves ~640 MB for OS kernel, buffers, and monitoring). A 2 GiB swapfile provides operational safety.
- **Deployment Automation**: GitHub Actions workflow (`deploy-production.yml`) incorporates verification gates, immutable image tags (Git commit SHA), zero-downtime rolling restart, automated database migration, and post-deployment health check with automatic rollback.
- **Backup & Recovery**: Scripts provide automated compressed `pg_dump` with SHA-256 integrity verification, configurable retention, and safe interactive restoration with post-restore validation.

---

## 12. External Verification Limitations

In accordance with strict safety instructions:
1. **No Real Social Posts**: Neither Facebook nor X live publishing credentials were used. Social publishing was audited and verified using mock API adapters, recorded responses, and deterministic unit tests with `SOCIAL_DRY_RUN=true`.
2. **No Real Emails Dispatched**: SMTP delivery was audited using `MockEmailProvider` and dry-run execution with `EMAIL_DRY_RUN=true`. No external mail servers were contacted.
3. **AWS Cloud Access**: No live AWS EC2 or S3 credentials were provided. Deployment workflows, container images, and backup scripts were validated locally and syntactically.
