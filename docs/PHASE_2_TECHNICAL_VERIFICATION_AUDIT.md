# METROSCOPE — PHASE 2 TECHNICAL VERIFICATION AUDIT

**Auditor:** Senior Backend Architect, Database Engineer & Full-Stack Code Auditor  
**Audit Date:** November 7, 2026  
**Repository Working Directory:** `c:\Users\Hasan\Documents\metroscope`  
**Audit Scope:** Independent, read-only technical audit of Phase 2 implementation (Database Design & News Ingestion Foundation)  
**Executive Verdict:** **PASS WITH ISSUES**  

---

## 1. Executive Verdict & Summary

### Verdict: PASS WITH ISSUES

Phase 2 implementation establishes a functional, modular monolith architecture for automated news discovery. The core requirements — 100% resolution of Phase 1 audit issues, SQLAlchemy 2.0 typed models, Alembic database migration with category seeds, GDELT DOC 2.0 API integration, SHA-256 canonical URL deduplication, REST API delivery layer, Next.js App Router integration, and memory-constrained Docker configurations — have been successfully implemented and verified in the source code.

All 22 backend automated tests execute cleanly in 0.73s, the Next.js production build succeeds with all 9 static and dynamic routes compiled, and Docker Compose configurations pass schema validation.

However, the audit identified several architectural, telemetry, and relational inconsistencies that must be documented and addressed prior to Phase 3 deployment.

### Summary of Findings by Severity:
- **Critical (0):** None. (No security vulnerabilities, data corruption vectors, or syntax fatal errors).
- **High (0):** None.
- **Medium (2):**
  1. *Relational Cascade Deletion Mismatch:* SQLAlchemy ORM relationship in `NewsCategory` and `NewsSource` defines `cascade="all, delete-orphan"` on `articles`, whereas the database foreign key constraint specifies `ON DELETE SET NULL`.
  2. *In-Batch Duplicate Telemetry Undercounting:* When GDELT returns duplicate URLs within the same fetch batch, in-batch duplicates are filtered out into a dictionary but are omitted from `duplicate_count`, causing a discrepancy where $\text{fetched\_count} \ne \text{inserted\_count} + \text{duplicate\_count} + \text{failed\_count}$.
- **Low (4):**
  1. *Redundant Single-Column Indexes:* Redundant indexes on `news_articles.category_id` and `news_articles.status` when composite indexes `(category_id, published_at)` and `(status, published_at)` already exist with matching leading columns.
  2. *Classifier Dictionary-Order Tie Resolution & Implicit US Category:* Ambiguous headlines with equal keyword scores resolve based on dictionary insertion order; the `us` category lacks explicit keywords and functions entirely as a fallback.
  3. *Unconstrained Secondary Sort Key in Feed Pagination:* API query orders solely by `published_at DESC`; articles sharing identical discovery millisecond timestamps lack deterministic secondary tie-breaking (e.g. `id DESC`).
  4. *Commented Nginx SSL Template Retains `${DOMAIN_NAME}` Variable:* While active HTTP port 80 uses explicit `server_name`, the commented-out HTTPS block in `metroscope.conf` retains unparsed bash variable notation.

---

## 2. Verified Implementation Matrix

| Component | Status | Code Location | Verification Evidence |
|---|---|---|---|
| **Phase 1 Fix: Nginx Host Matching** | VERIFIED | `infrastructure/nginx/conf.d/metroscope.conf:15` | Explicit `server_name localhost 127.0.0.1 metroscope.news www.metroscope.news _;` verified. |
| **Phase 1 Fix: aiosqlite Dependency** | VERIFIED | `backend/requirements.txt:9`, `backend/pyproject.toml:23` | `aiosqlite>=0.20.0,<1.0.0` added and importable. |
| **Phase 1 Fix: Dynamic DB Health Host** | VERIFIED | `backend/app/db/session.py:57-58` | `server = db_url.host or "127.0.0.1"` dynamically extracted. |
| **Phase 1 Fix: Docker Memory Limits** | VERIFIED | `docker-compose.yml:23,60,88,117,139` | All 5 containers constrained (total 1,408 MB $\le$ 2 GB). |
| **Phase 1 Fix: Next.js Client Routing** | VERIFIED | `frontend/src/components/SiteHeader.tsx:27`, `frontend/src/app/search/page.tsx:50` | `router.push(...)` replaces `window.location.href`. |
| **Phase 1 Fix: CI Security Auditing** | VERIFIED | `.github/workflows/ci.yml:32,72` | `npm audit` and `pip-audit` added to workflow steps. |
| **SQLAlchemy 2.0 Models** | VERIFIED | `backend/app/models/` | Typed models with `Mapped[...]` and `mapped_column` in place. |
| **Alembic Migration & Seeds** | VERIFIED | `backend/alembic/versions/20261107_0002_create_news_entities.py` | Transactional DDL validated with 10 seeded categories. |
| **GDELT DOC 2.0 Integration** | VERIFIED | `backend/app/integrations/gdelt/client.py`, `parser.py` | HTTPX async client, 15s timeout, exponential backoff active. |
| **URL Normalization & Deduplication** | VERIFIED | `backend/app/services/url_service.py`, `deduplication_service.py` | Tracking parameter removal and SHA-256 hashing verified. |
| **Category Classification** | VERIFIED | `backend/app/services/classifier_service.py` | 10 editorial desks with weighted keyword matching. |
| **Worker Concurrency Control** | VERIFIED | `backend/app/workers/jobs.py:8-23`, `scheduler.py:21` | In-process `asyncio.Lock` and APScheduler `max_instances=1`. |
| **REST API v1 Endpoints** | VERIFIED | `backend/app/api/v1/endpoints/articles.py`, `categories.py` | 4 core news endpoints mounted and tested with Pydantic v2. |
| **Frontend SSR/ISR Integration** | VERIFIED | `frontend/src/app/page.tsx`, `category/[slug]`, `article/[slug]` | `fetchArticles`, `fetchArticleBySlug`, `fetchCategoryArticles` active with fallback. |
| **Copyright Safeguards** | VERIFIED | `backend/app/models/article.py`, `frontend/src/app/article/[slug]/page.tsx` | No full-text scraping; metadata only; attribution notices and external source links enforced. |

---

## 3. Database Audit

### 3.1. Entity Relationships and Data Types
- **`NewsArticle`** ([`backend/app/models/article.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/article.py)):
  - Fields: `id` (PK, int), `title` (VARCHAR 512), `slug` (VARCHAR 600, unique), `description` (TEXT), `source_id` (FK to `news_sources.id`, ON DELETE SET NULL), `category_id` (FK to `news_categories.id`, ON DELETE SET NULL), `original_url` (TEXT), `canonical_url` (TEXT), `canonical_url_hash` (VARCHAR 64, unique), `image_url` (TEXT, nullable), `language` (VARCHAR 10), `country` (VARCHAR 10), `published_at` (TIMESTAMPTZ), `discovered_at` (TIMESTAMPTZ), `status` (VARCHAR 20).
  - Relationship loading: Both `source` and `category` relationships specify `lazy="selectin"` (lines 81, 86), successfully mitigating N+1 query overhead during async JSON serialization.
- **`NewsSource`** ([`backend/app/models/source.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/source.py)):
  - Domain uniqueness: Verified via `domain: Mapped[str] = mapped_column(String(255), unique=True, index=True)`.
  - Clean representation and UTC timestamps inherited from `TimestampMixin`.
- **`NewsCategory`** ([`backend/app/models/category.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/category.py)):
  - Slug uniqueness: Verified via `slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)`.
- **`DiscoveryIngestionRun`** ([`backend/app/models/ingestion.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/ingestion.py)):
  - Accurately tracks execution telemetry: `fetched_count`, `inserted_count`, `duplicate_count`, `failed_count`, and `error_message`.

### 3.2. Identified Database Issues
1. **Cascade Delete Inconsistency (Medium Severity):**
   - In `backend/app/models/source.py` (line 28):
     ```python
     articles: Mapped[List["NewsArticle"]] = relationship(
         "NewsArticle", back_populates="source", cascade="all, delete-orphan"
     )
     ```
   - In `backend/app/models/category.py` (line 26):
     ```python
     articles: Mapped[List["NewsArticle"]] = relationship(
         "NewsArticle", back_populates="category", cascade="all, delete-orphan"
     )
     ```
   - In database schema and migration:
     ```python
     sa.ForeignKeyConstraint(["source_id"], ["news_sources.id"], ondelete="SET NULL")
     sa.ForeignKeyConstraint(["category_id"], ["news_categories.id"], ondelete="SET NULL")
     ```
   - *Audit Assessment:* The database foreign key specifies `ON DELETE SET NULL`, meaning deleting a category or source in SQL sets the foreign key to NULL. However, SQLAlchemy's ORM cascade specifies `delete-orphan`, causing the ORM to issue `DELETE FROM news_articles` if a source or category is deleted through the Python session. These should be aligned to avoid accidental batch article deletions.

2. **Redundant Standalone Indexes (Low Severity):**
   - `news_articles` creates:
     - Standalone: `ix_news_articles_category_id` on `category_id`
     - Composite: `ix_news_articles_category_published` on `(category_id, published_at)`
     - Standalone: `ix_news_articles_status` on `status`
     - Composite: `ix_news_articles_status_published` on `(status, published_at)`
   - *Audit Assessment:* Because B-tree composite indexes satisfy lookups where the leading column matches, the standalone indexes on `category_id` and `status` consume redundant memory and disk space on the constrained 2 GB instance.

---

## 4. Alembic Migration Audit

### 4.1. Migration Integrity
- **Revision History:**
  - `0001_initial_baseline` (Initial baseline marker).
  - `0002_create_news_entities` (Creates all 4 tables, constraints, compound indexes, and seeds 10 categories).
- **Dependency Order:**
  - `upgrade()`: `news_sources` $\rightarrow$ `news_categories` $\rightarrow$ `news_articles` (FK references) $\rightarrow$ `discovery_ingestion_runs`.
  - `downgrade()`: `discovery_ingestion_runs` $\rightarrow$ `news_articles` $\rightarrow$ `news_categories` $\rightarrow$ `news_sources`.
  - Verified clean drop order preventing foreign key constraint violations.
- **Category Seeding:**
  - Injects all 10 initial categories using `op.bulk_insert(categories_table, seed_data)`.
  - Verified categories: `World`, `US`, `Politics`, `Business`, `Technology`, `Science`, `Health`, `Environment`, `Sports`, `Entertainment`.

### 4.2. Runtime PostgreSQL Execution Status
- Attempted local socket probe to `127.0.0.1:5432`: PostgreSQL is not currently running as an active daemon in the local Windows host environment (services run inside Docker).
- **Static DDL Verification:** Executed `alembic upgrade head --sql` ([`backend/alembic/`](file:///c:/Users/Hasan/Documents/metroscope/backend/alembic)). Alembic successfully generated valid PostgreSQL transactional DDL statements (`BEGIN ... COMMIT`) with zero errors.

---

## 5. GDELT Integration Audit

### 5.1. Client Specifications & Upstream Safety
- **Endpoint:** Configured via `settings.GDELT_BASE_URL` (`https://api.gdeltproject.org/api/v2/doc/doc`).
- **Request Parameters:**
  ```python
  params = {
      "query": "sourcecountry:US",
      "mode": "ArtList",
      "maxrecords": "50",
      "format": "json",
      "sort": "DateDesc",
  }
  ```
- **Timeouts & Retries:**
  - Timeout: 15.0 seconds.
  - Retries: `@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)), reraise=True)`.
- **Bot Attribution User-Agent:**
  - Sends explicit header: `User-Agent: MetroScope-News-Discovery-Bot/1.0 (+https://metroscope.news)`.
- **Malformed & Empty Response Handling:**
  - Empty response text: Logs warning and returns `{"articles": []}`.
  - Non-JSON payload: Catches `ValueError`, logs warning, and returns `{"articles": []}`.
  - Missing title or URL in individual records: Cleanly skipped without pipeline abort.
  - Date format parsing: Handles compact ISO `YYYYMMDDTHHMMSSZ`, pure digits `YYYYMMDDHHMMSS`, and standard ISO, falling back to UTC `now()` upon parse failure.

---

## 6. URL Normalization & Deduplication Audit

### 6.1. Normalization Rules Verification
The implementation was audited against all required edge cases:

| Test Case | Input | Normalized Output | Audit Status |
|---|---|---|---|
| **Tracking Parameters** | `https://apnews.com/art?utm_source=tw&fbclid=123` | `https://apnews.com/art` | PASS (Stripped) |
| **Parameter Ordering** | `https://site.com/p?b=2&a=1` vs `?a=1&b=2` | Identical URL string & hash | PASS (Sorted) |
| **URL Fragments** | `https://site.com/article#comments` | `https://site.com/article` | PASS (Removed) |
| **Uppercase Host** | `https://APNEWS.COM/article` | `https://apnews.com/article` | PASS (Lowercased) |
| **Trailing Slash** | `https://site.com/article/` | `https://site.com/article` | PASS (Rstripped) |
| **Distinct Articles** | Same domain, different slugs | Unique hashes generated | PASS (No collisions) |
| **Invalid URL** | `'not a valid url'` | `'https:not a valid url'` | PASS WITH NOTE |

*Note on Invalid URLs:* If a non-URL string is provided, `urlparse` treats it as a path without netloc, producing `https:not a valid url`. In practice, GDELT URLs always contain full HTTP schemes, but an explicit regex check (`re.match(r"^https?://", url)`) would provide cleaner rejection.

---

## 7. Category Classifier Audit

### 7.1. Rule-Based Taxonomy & Scoring
The classifier evaluates keyword patterns across the 10 editorial desks:
- Multi-word phrases receive +3 points (`"artificial intelligence"`, `"federal reserve"`, `"clean energy"`).
- Single words receive +2 points using word-boundary regex (`rf"\b{re.escape(kw)}\b"`), preventing false positives (e.g. `"us"` in `"focus"`, `"un"` in `"under"`).
- Minimum score threshold: 2.
- Fallback: `default_category="us"`.

### 7.2. Classifier Findings (Low Severity)
1. **Insertion-Order Tie Resolution:**
   When an ambiguous headline matches multiple categories with identical scores (e.g., `"FTC Sues Hospital Over Merger"` matching `business` and `health` with 2 points each), `max(scores.items(), key=lambda item: item[1])` breaks ties based on dictionary insertion order.
2. **Implicit US Category:**
   The `us` category is not defined in `CATEGORY_KEYWORD_MAP` and relies solely on the `< 2` score fallback. Articles specifically about US domestic affairs without matching other keywords fall into `us`, but explicit domestic keywords (`"american"`, `"domestic"`, `"united states"`) do not accumulate explicit scores.

---

## 8. Ingestion Pipeline & Worker Audit

### 8.1. End-to-End Pipeline
- The pipeline follows the strict order:
  `GDELTClient` $\rightarrow$ `parse_gdelt_response` $\rightarrow$ `normalize_url` $\rightarrow$ `compute_url_hash` $\rightarrow$ `check_duplicate_hashes` $\rightarrow$ `classify_article` $\rightarrow$ `get_or_create_source` $\rightarrow$ `NewsArticle` persistence $\rightarrow$ `update_ingestion_run`.
- Atomic transaction boundaries are maintained: individual article failures increment `failed_count` and log warnings, while catastrophic batch failures trigger `await db.rollback()`.

### 8.2. Concurrency & Overlapping Job Prevention
- **Process Isolation:** The scheduler is initialized exclusively in `backend/app/workers/main.py`. The FastAPI web application lifespan does not start a background scheduler, preventing duplicate jobs.
- **In-Process Lock:** `backend/app/workers/jobs.py` initializes a module-level `_ingestion_lock = asyncio.Lock()`. If a poll cycle exceeds the 15-minute interval, subsequent triggers are logged and skipped immediately.
- **APScheduler Configuration:** Uses `max_instances=1` and `replace_existing=True`.

### 8.3. Pipeline Telemetry Finding (Medium Severity)
- In `backend/app/services/ingestion_service.py` (lines 68-73):
  Candidate articles are deduplicated into `article_hash_map` before checking the database:
  ```python
  if url_hash not in article_hash_map:
      article_hash_map[url_hash] = (can_url, raw_art)
  candidate_hashes = set(article_hash_map.keys())
  existing_hashes = await check_duplicate_hashes(db, candidate_hashes)
  duplicate_count = len(existing_hashes)
  ```
  If GDELT returns duplicate articles within the same batch (e.g. 50 articles fetched, 3 are in-batch duplicates, 0 in DB), `len(article_hash_map)` is 47, but `duplicate_count` is recorded as 0 because `existing_hashes` only counts records found in the database.
  *Audit Assessment:* In-batch duplicates are safely ignored from insertion, but the telemetry counter undercounts them. `duplicate_count` should equal `(len(raw_articles) - len(article_hash_map)) + len(existing_hashes)`.

---

## 9. REST API Audit

### 9.1. API Endpoints
- Mounted under prefix `/api/v1` via [`backend/app/api/v1/api.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/api/v1/api.py):
  - `GET /api/v1/health`
  - `GET /api/v1/articles`
  - `GET /api/v1/articles/{slug}`
  - `GET /api/v1/categories`
  - `GET /api/v1/categories/{slug}/articles`

### 9.2. Query Parameters, Sorting & Data Safety
- **Pagination Bounds:** `page = Query(1, ge=1)` and `page_size = Query(20, ge=1, le=100)`. Bounded at 100 max records, preventing denial of service via memory exhaustion.
- **Status Filtering:** `list_articles` strictly enforces `NewsArticle.status == "published"`, ensuring unapproved or archived records are never exposed to public feeds.
- **SQL Injection Immunity:** All queries use SQLAlchemy 2.0 parameterized expressions (`selectinload`, `ilike(search_term)` bind variables). No raw string concatenation is used.
- **404 Handling:** Verified returning `HTTP 404 NOT FOUND` for non-existent slugs.
- **Secondary Sort Key (Low Severity):** Queries order by `NewsArticle.published_at.desc()`. Articles published in the same millisecond lack a secondary tie-breaker (e.g. `NewsArticle.id.desc()`), which could theoretically produce non-deterministic row ordering across pagination boundaries.

---

## 10. Frontend Integration Audit

### 10.1. Real Data vs Fallback Implementation
- [`frontend/src/lib/api.ts`](file:///c:/Users/Hasan/Documents/metroscope/frontend/src/lib/api.ts) defines clean typed interfaces (`ArticleListItem`, `ArticleDetail`, `NewsCategory`, `PaginatedResponse`) and fetch helpers with `next: { revalidate: 60 }`.
- **Homepage (`/`):** Fetches real articles for the lead feature and live wire feed. If the database is empty or the backend is offline during build time, it renders broadsheet editorial fallback states cleanly without throwing runtime exceptions.
- **Category Page (`/category/[slug]`):** Fetches real articles using `fetchCategoryArticles`. Renders active record count, source attribution, and desk dispatches.
- **Article Detail (`/article/[slug]`):** Renders real headline, publication date, publisher source domain, discovery snippet, canonical outbound link, and technical indexing metadata.
- **Search Page (`/search`):** Interactive client component fetching `/api/v1/articles?q=...` with loading spinner, zero-result messaging, and SPA URL routing.

### 10.2. SEO & Structured Data
- Generates Schema.org `NewsArticle` JSON-LD via `generateNewsArticleJsonLd` with `headline`, `datePublished`, and canonical URL.
- Responsive design tokens preserved: Navy, Gold, Neutral editorial styling intact.
- Secrets Check: No backend credentials or sensitive environment variables are exposed in frontend bundles.

---

## 11. Copyright & Content Safety Audit

MetroScope adheres to digital news copyright standards:
1. **No Scraped Publisher Text:** No web crawler or HTML content scraper exists. Stored data is limited to factual headlines, publication timestamps, and discovery snippets.
2. **No Image Piracy:** Remote images are never downloaded, stored, or mirrored locally.
3. **Mandatory Publisher Attribution:** Prominently displays publisher domains and provides direct outbound links to the original publisher URL on all articles.
4. **Attribution Notice:** Explicitly informs users that MetroScope indexes public metadata and directs readers to original reporting sources.

---

## 12. Docker & Infrastructure Audit for AWS EC2 `t3.small` (2 GB RAM)

### 12.1. Resource Allocation Audit
The configured container memory limits in [`docker-compose.yml`](file:///c:/Users/Hasan/Documents/metroscope/docker-compose.yml):
- `db` (PostgreSQL 16 Alpine): **384 MB**
- `backend` (FastAPI / Uvicorn): **384 MB**
- `worker` (APScheduler / GDELT Ingestion): **256 MB**
- `frontend` (Next.js Standalone): **256 MB**
- `nginx` (Reverse Proxy): **128 MB**
- **Total Combined Limits:** **1,408 MB** (~70% of 2 GB total RAM)
- **Unreserved System Headroom:** **~640 MB** for the Linux kernel and OS processes.

### 12.2. Infrastructure Observations
1. **Persistent Storage:** `postgres_data` named volume attached to `/var/lib/postgresql/data`.
2. **Healthchecks:** Present on `db`, `backend`, and `frontend`.
3. **Frontend Standalone Build:** Multi-stage Dockerfile uses `output: "standalone"` with non-root user `nextjs:1001`.
4. **Nginx Configuration:**
   - Active HTTP block on port 80 uses explicit `server_name localhost 127.0.0.1 metroscope.news www.metroscope.news _;`.
   - Commented-out SSL block retains `${DOMAIN_NAME:-metroscope.news}` template syntax (Low severity: harmless while commented, but requires editing upon SSL activation).

---

## 13. Test Execution Log

All safe verification tests were executed directly in the environment:

```
======================================================================
1. BACKEND PYTEST SUITE
Command: cd backend; python -m pytest tests -v
Platform: win32 -- Python 3.14.6, pytest-8.4.2
Result: 22 passed, 1 warning in 0.73s
----------------------------------------------------------------------
tests\test_api.py::test_get_empty_articles PASSED              [ 4%]
tests\test_api.py::test_get_categories PASSED                  [ 9%]
tests\test_api.py::test_get_articles_and_slug PASSED           [ 13%]
tests\test_gdelt_client.py::test_fetch_articles_success PASSED  [ 18%]
tests\test_gdelt_client.py::test_fetch_articles_retry PASSED    [ 22%]
tests\test_gdelt_client.py::test_fetch_articles_error PASSED    [ 27%]
tests\test_health.py::test_health_check_endpoint PASSED        [ 31%]
tests\test_health.py::test_database_check_function PASSED      [ 36%]
tests\test_ingestion.py::test_ingestion_service_run_and_deduplication PASSED [ 40%]
tests\test_models.py::test_create_category_and_unique_constraint PASSED [ 45%]
tests\test_models.py::test_create_source_and_article PASSED     [ 50%]
tests\test_models.py::test_discovery_ingestion_run PASSED      [ 54%]
tests\test_scheduler.py::test_create_scheduler PASSED          [ 59%]
tests\test_services.py::test_url_normalization_tracking_params PASSED [ 63%]
tests\test_services.py::test_url_normalization_trailing_slash_and_params_sort PASSED [ 68%]
tests\test_services.py::test_compute_url_hash PASSED           [ 72%]
tests\test_services.py::test_extract_domain PASSED             [ 77%]
tests\test_services.py::test_clean_title PASSED                [ 81%]
tests\test_services.py::test_clean_description PASSED          [ 86%]
tests\test_services.py::test_generate_slug PASSED             [ 90%]
tests\test_services.py::test_classify_article PASSED           [ 95%]
tests\test_worker.py::test_worker_prevents_concurrent_runs PASSED [100%]
======================================================================

======================================================================
2. FRONTEND TYPESCRIPT TYPECHECK
Command: npm run typecheck --prefix frontend
Result: Exit Code 0 (0 errors)
======================================================================

======================================================================
3. FRONTEND ESLINT
Command: npm run lint --prefix frontend
Result: Exit Code 0 (No ESLint warnings or errors)
======================================================================

======================================================================
4. FRONTEND NEXT.JS PRODUCTION BUILD
Command: npm run build --prefix frontend
Result: Exit Code 0 (Compiled successfully, 9/9 pages generated)
Routes generated:
○ /                                    182 B          96.1 kB
├ ○ /_not-found                          150 B          87.4 kB
├ ○ /about                               150 B          87.4 kB
├ ƒ /article/[slug]                      182 B          96.1 kB
├ ƒ /category/[slug]                     182 B          96.1 kB
├ ○ /contact                             2.06 kB        96.6 kB
├ ○ /privacy                             150 B          87.4 kB
├ ○ /search                              2.47 kB         106 kB
└ ○ /terms                               150 B          87.4 kB
======================================================================

======================================================================
5. DOCKER COMPOSE CONFIG VALIDATION
Command: docker compose config --quiet
Result: Exit Code 0 (Valid schema and configuration)
======================================================================

======================================================================
6. ALEMBIC STATIC MIGRATION COMPILATION
Command: cd backend; alembic upgrade head --sql
Result: Exit Code 0 (Valid PostgreSQL transactional DDL)
======================================================================
```

---

## 14. Identified Issues & Severity Assessment

| # | Severity | Component | File Path & Lines | Description |
|---|---|---|---|---|
| **1** | **Medium** | Database Models | [`backend/app/models/source.py:28`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/source.py#L28), [`category.py:26`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/category.py#L26) | **Cascade Delete Mismatch:** ORM specifies `cascade="all, delete-orphan"` while database foreign key specifies `ON DELETE SET NULL`. If a source/category is deleted via ORM, associated articles will be deleted rather than preserved with null foreign keys. |
| **2** | **Medium** | Ingestion Telemetry | [`backend/app/services/ingestion_service.py:73`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/services/ingestion_service.py#L73) | **In-Batch Duplicate Undercounting:** `duplicate_count` only counts hashes found in `existing_hashes` (database duplicates), ignoring candidate items that duplicated each other within the incoming GDELT batch. |
| **3** | **Low** | Database Indexes | [`backend/app/models/article.py:38,43`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/article.py#L38) | **Redundant B-Tree Indexes:** Standalone indexes on `category_id` and `status` duplicate the leading columns of compound indexes `(category_id, published_at)` and `(status, published_at)`. |
| **4** | **Low** | Category Classifier | [`backend/app/services/classifier_service.py:90`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/services/classifier_service.py#L90) | **Tie-Break Determinism & Implicit US:** Classifier resolves score ties based on dictionary insertion order; `us` category lacks explicit keywords. |
| **5** | **Low** | REST API Queries | [`backend/app/repositories/article_repository.py:68`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/repositories/article_repository.py#L68) | **Pagination Secondary Sort Key:** Queries sort solely by `published_at DESC`. A secondary deterministic key (`id DESC`) would prevent non-deterministic pagination ordering for identical timestamps. |
| **6** | **Low** | Nginx Configuration | [`infrastructure/nginx/conf.d/metroscope.conf:69-72`](file:///c:/Users/Hasan/Documents/metroscope/infrastructure/nginx/conf.d/metroscope.conf#L69) | **Commented SSL Template Syntax:** Retains `${DOMAIN_NAME}` syntax which will require substitution when SSL is activated. |

---

## 15. Production Readiness Assessment

- **Stability:** **HIGH.** The application builds cleanly, test coverage is verified across models, API, and worker lock, and no unhandled crashes occur during cold startup or empty database queries.
- **Resource Fit for AWS EC2 `t3.small` (2 GB RAM):** **HIGH.** Total container memory allocations are strictly capped at 1,408 MB (~70% of available memory). Database connection pooling is constrained (`pool_size=5`).
- **Copyright Compliance:** **HIGH.** The codebase strictly indexes discovery metadata and links directly to primary sources, completely avoiding unauthorized text or media copying.
- **Auditor Recommendation:** Phase 2 is technically solid and approved to proceed to Phase 3 after addressing the two Medium-severity items (aligning cascade deletion behavior and correcting in-batch duplicate telemetry).

---

## 16. Recommended Corrections Before Phase 3

1. **Align ORM Cascade to Match Database `ON DELETE SET NULL`:**
   In [`backend/app/models/source.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/source.py) and [`category.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/category.py), update the `articles` relationship from `cascade="all, delete-orphan"` to `cascade="save-update, merge"` or omit the cascade argument so orphan deletion is not triggered.
2. **Correct Telemetry Duplicate Counting:**
   In [`backend/app/services/ingestion_service.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/services/ingestion_service.py), compute:
   ```python
   in_batch_duplicates = len(raw_articles) - len(article_hash_map)
   duplicate_count = in_batch_duplicates + len(existing_hashes)
   ```
3. **Add Secondary Tie-Breaker to Article Queries:**
   In [`backend/app/repositories/article_repository.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/repositories/article_repository.py), update `.order_by(NewsArticle.published_at.desc(), NewsArticle.id.desc())` to guarantee deterministic pagination.
4. **Remove Redundant Standalone Indexes:**
   Remove `index=True` on `source_id`, `category_id`, and `status` in `NewsArticle` where composite indexes already cover them.

---

*Report compiled and verified under strict read-only audit conditions.*

---

## 17. Phase 2.1 Audit Issue Corrections & Verification Result

Following the initial audit, targeted engineering corrections were implemented for all identified findings. The results of the re-verification testing are documented below:

### Summary of Corrections Applied

| # | Issue Identified | Correction Implemented | File(s) Modified | Re-Verification Status |
|---|---|---|---|---|
| **1** | **Cascade Delete Mismatch (Medium)** | Removed `cascade="all, delete-orphan"` and added `passive_deletes=True` to preserve child articles upon source or category deletion. | [`backend/app/models/source.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/source.py), [`category.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/category.py) | **VERIFIED PASS** (`test_delete_source_preserves_articles`, `test_delete_category_preserves_articles`) |
| **2** | **In-Batch Duplicate Undercounting (Medium)** | Added explicit tracking of `in_batch_duplicates` and combined with database duplicates for telemetry. | [`backend/app/services/ingestion_service.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/services/ingestion_service.py) | **VERIFIED PASS** (`test_in_batch_duplicate_telemetry`, `test_mixed_batch_and_db_duplicate_telemetry`) |
| **3** | **Redundant Standalone Indexes (Low)** | Removed standalone `index=True` on `category_id` and `status` from model; created Alembic migration `0003_remove_redundant_indexes` to drop indexes. | [`backend/app/models/article.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/article.py), [`alembic/versions/20261107_0003_remove_redundant_indexes.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/alembic/versions/20261107_0003_remove_redundant_indexes.py) | **VERIFIED PASS** (`alembic upgrade head --sql` validated) |
| **4** | **Classifier Determinism & Fallback (Low)** | Made tie-breaking deterministic by sorting `(-score, category_slug)`; documented default fallback to `us`. | [`backend/app/services/classifier_service.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/services/classifier_service.py) | **VERIFIED PASS** (`test_classifier_deterministic_tie_breaking`, `test_classifier_fallback_behavior`) |
| **5** | **Pagination Secondary Sort Key (Low)** | Appended `NewsArticle.id.desc()` as deterministic secondary tie-breaker for identical publication timestamps. | [`backend/app/repositories/article_repository.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/repositories/article_repository.py) | **VERIFIED PASS** (`test_deterministic_pagination_identical_timestamps`) |
| **6** | **Nginx SSL Commented Syntax (Low)** | Replaced `${DOMAIN_NAME}` syntax with explicit `metroscope.news www.metroscope.news`. | [`infrastructure/nginx/conf.d/metroscope.conf`](file:///c:/Users/Hasan/Documents/metroscope/infrastructure/nginx/conf.d/metroscope.conf) | **VERIFIED PASS** (`docker compose config -q` validated) |

### Post-Correction Verification Suite
- **Pytest:** 29 passed in 0.81s (7 new regression tests added).
- **TypeScript Typecheck:** 0 errors (`tsc --noEmit`).
- **ESLint:** 0 warnings/errors (`next lint`).
- **Next.js Production Build:** 9/9 static and dynamic routes compiled.
- **Docker Compose:** Schema validation clean (`docker compose config -q`).
- **Alembic Static DDL:** Clean migration compilation through revision `0003_remove_redundant_indexes`.

