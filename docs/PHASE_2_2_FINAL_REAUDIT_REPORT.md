# METROSCOPE — PHASE 2.2 FINAL READ-ONLY RE-AUDIT REPORT

**Auditor:** Independent Senior Backend Engineer, PostgreSQL Database Auditor & QA Engineer  
**Date:** November 7, 2026  
**Audit Type:** Strict Read-Only Verification & Re-Audit  
**Workspace:** `c:\Users\Hasan\Documents\metroscope`  
**Reference Documents:**
- `docs/PHASE_2_TECHNICAL_VERIFICATION_AUDIT.md`
- `docs/PHASE_2_1_CORRECTION_REPORT.md`
- `docs/PHASE_2_IMPLEMENTATION_REPORT.md`

---

## 1. Executive Verdict & Final Recommendation

### Executive Verdict: **PASS**

### Final Recommendation: **READY FOR PHASE 3**

All six issues identified in the initial Phase 2 Technical Verification Audit have been completely resolved, verified in source code, and substantiated through automated test suites. 

No regressions were observed: all 29 backend unit and integration tests execute cleanly in 1.12s, the Next.js production build succeeds with all 9 static and dynamic routes compiled, Alembic static DDL generation confirms schema integrity through migration `0003_remove_redundant_indexes`, and Docker Compose memory constraints adhere strictly to the 2 GB RAM budget of the target AWS EC2 `t3.small` instance.

Strict scope boundaries remain fully respected: no unauthorized reader/author accounts, comments, social auto-publishing, full-text web scraping, or heavy infrastructure dependencies (Redis, Celery, RabbitMQ) have been introduced.

---

## 2. Verification Methodology

The re-audit was executed under strict read-only constraints:
1. **Static Source Code Inspection:** Every modified file, model, schema, service, repository, Dockerfile, Nginx configuration, and migration script was inspected directly on disk.
2. **Deterministic Behavior Testing:** Analyzed mathematical and logical algorithms for tie-breaking, URL normalization, deduplication invariants, and secondary sorting.
3. **Automated Test Execution:** Executed full regression test suites (Pytest, TypeScript compiler, ESLint, Next.js build, Docker Compose validation, Alembic static DDL generation) without mocking bypasses.
4. **PostgreSQL Environment Assessment:** Probed local runtime infrastructure to distinguish executed database tests from engine-level capabilities.

---

## 3. Independent Verification of Phase 2.1 Corrections

| # | Audit Item | Prior Audit Finding | Correction Verified in Code | Verification Evidence | Re-Audit Verdict |
|---|---|---|---|---|:---:|
| **1** | **ORM Cascade Alignment** | ORM defined `cascade="all, delete-orphan"` on `articles`, conflicting with database `ON DELETE SET NULL`. | `NewsSource.articles` and `NewsCategory.articles` updated to `passive_deletes=True`. | [`backend/app/models/source.py:28`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/source.py#L28), [`category.py:26`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/category.py#L26). Deleting source/category preserves articles. | **PASS** |
| **2** | **Ingestion Duplicate Telemetry** | Duplicates within the same GDELT batch were filtered out but omitted from `duplicate_count`. | `IngestionService.run_discovery` tracks `in_batch_duplicates` and sums with `db_duplicates`. | [`backend/app/services/ingestion_service.py:63,81`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/services/ingestion_service.py#L63). Invariant $\text{fetched} = \text{inserted} + \text{duplicate} + \text{failed}$ verified. | **PASS** |
| **3** | **Deterministic Secondary Sorting** | Feed queries sorted solely by `published_at DESC`, risking non-deterministic ordering for identical timestamps. | Appended `NewsArticle.id.desc()` as deterministic secondary tie-breaker. | [`backend/app/repositories/article_repository.py:68`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/repositories/article_repository.py#L68). Page isolation verified in `test_api.py`. | **PASS** |
| **4** | **Redundant Database Indexes** | Standalone indexes on `category_id` and `status` duplicated compound indexes `(category_id, published_at)` and `(status, published_at)`. | Removed `index=True` in model; created migration `0003_remove_redundant_indexes` dropping both standalone indexes. | [`backend/app/models/article.py:40,70`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/article.py#L40), [`alembic/versions/20261107_0003_remove_redundant_indexes.py:23-24`](file:///c:/Users/Hasan/Documents/metroscope/backend/alembic/versions/20261107_0003_remove_redundant_indexes.py#L23). | **PASS** |
| **5** | **Classifier Determinism** | Category tie-breaking relied on dictionary iteration order; `us` fallback lacked explicit documentation. | Sorted candidates by `(-score, category_slug)`; documented default fallback to `us`. | [`backend/app/services/classifier_service.py:80-101`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/services/classifier_service.py#L80). Alphabetical tie-breaking verified in `test_services.py`. | **PASS** |
| **6** | **Nginx SSL Configuration Cleanup** | Commented SSL template block retained `${DOMAIN_NAME:-metroscope.news}` template syntax. | Cleaned up commented block with explicit domain names matching line 15. | [`infrastructure/nginx/conf.d/metroscope.conf:69-72`](file:///c:/Users/Hasan/Documents/metroscope/infrastructure/nginx/conf.d/metroscope.conf#L69). Zero unparsed template variables remain. | **PASS** |

---

## 4. PostgreSQL Runtime Verification Status Disclosure

> [!IMPORTANT]
> **PostgreSQL Runtime Disclosure:**  
> A dedicated standalone PostgreSQL daemon was not active on host port `5432` during this audit session (the database runs inside the containerized Docker environment `metroscope-db` via `docker-compose.yml`).  
> Consequently:
> 1. Automated unit and integration tests executed against SQLite in-memory (`sqlite+aiosqlite:///:memory:`).
> 2. Alembic migration operations and schema generation were validated through static SQL compilation (`alembic upgrade head --sql`) using the real PostgreSQL dialect (`PostgresqlImpl`).
> 3. True PostgreSQL engine-level runtime behavior (such as physical index page sizes and database-enforced `ON DELETE SET NULL` cascade execution under live concurrency) will occur upon container startup in the deployment environment.

---

## 5. Detailed Audit Findings

### 5.1. Audit 1 — ORM Cascade & Foreign Key Behavior
- **Inspection:** Inspected [`backend/app/models/source.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/source.py), [`backend/app/models/category.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/category.py), and [`backend/app/models/article.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/article.py).
- **Findings:**
  - `cascade="all, delete-orphan"` was removed from both parent entities.
  - `passive_deletes=True` is correctly declared on `NewsSource.articles` (line 28) and `NewsCategory.articles` (line 26).
  - In `NewsArticle`, foreign keys `source_id` and `category_id` are explicitly declared `nullable=True` with `ondelete="SET NULL"`.
  - Regression tests `test_delete_source_preserves_articles` and `test_delete_category_preserves_articles` in [`backend/tests/test_models.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/tests/test_models.py#L73) confirm that deleting a parent source or category leaves associated article rows intact.

### 5.2. Audit 2 — Ingestion Duplicate Telemetry Invariant
- **Inspection:** Inspected [`backend/app/services/ingestion_service.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/services/ingestion_service.py) lines 60–165.
- **Mathematical Invariant Verification:**
  - Let $N$ be `len(raw_articles)`.
  - Each record is partitioned during preprocessing:
    - If `normalize_url(raw_art.url)` is empty $\rightarrow$ `invalid_url_count += 1`.
    - Else if `url_hash in article_hash_map` $\rightarrow$ `in_batch_duplicates += 1`.
    - Else $\rightarrow$ inserted into `article_hash_map`.
    - Thus: $N = \text{invalid\_url\_count} + \text{in\_batch\_duplicates} + \text{len(article\_hash\_map)}$.
  - Candidate hashes are checked against database:
    - $\text{db\_duplicates} = \text{len(existing\_hashes)}$.
    - $\text{non\_duplicate\_candidates} = \text{len(article\_hash\_map)} - \text{db\_duplicates}$.
  - During insertion of non-duplicate candidates:
    - Successful insert $\rightarrow$ `inserted_count += 1`.
    - Title cleaning failure or exception $\rightarrow$ `failed_count += 1`.
  - Total accounting:
    $$\begin{aligned}
    \text{inserted\_count} + \text{duplicate\_count} + \text{failed\_count} &= \text{inserted\_count} + (\text{in\_batch\_duplicates} + \text{db\_duplicates}) + (\text{invalid\_url\_count} + \text{failed\_inserts}) \\
    &= (\text{inserted\_count} + \text{failed\_inserts}) + \text{db\_duplicates} + \text{in\_batch\_duplicates} + \text{invalid\_url\_count} \\
    &= \text{len(article\_hash\_map)} + \text{in\_batch\_duplicates} + \text{invalid\_url\_count} \\
    &= N = \text{fetched\_count}
    \end{aligned}$$
  - The invariant strictly holds across all cases.
  - Regression tests `test_in_batch_duplicate_telemetry` and `test_mixed_batch_and_db_duplicate_telemetry` passed.

### 5.3. Audit 3 — Deterministic Pagination
- **Inspection:** Inspected [`backend/app/repositories/article_repository.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/repositories/article_repository.py) line 68.
- **Findings:**
  - Query ordering is explicitly defined:
    ```python
    .order_by(NewsArticle.published_at.desc(), NewsArticle.id.desc())
    ```
  - Primary sort remains `published_at DESC`.
  - Secondary sort `id DESC` guarantees deterministic tie-breaking.
  - Regression test `test_deterministic_pagination_identical_timestamps` verified that four articles with identical timestamps split across page 1 and page 2 return mutually exclusive sets with non-overlapping, strictly descending IDs.

### 5.4. Audit 4 — Database Indexes & Migration History
- **Inspection:** Inspected migration chain in [`backend/alembic/versions/`](file:///c:/Users/Hasan/Documents/metroscope/backend/alembic/versions/).
- **Findings:**
  - `0001_initial_baseline` $\rightarrow$ `0002_create_news_entities` $\rightarrow$ `0003_remove_redundant_indexes`.
  - Earlier migrations were not modified or rewritten.
  - In `0003_remove_redundant_indexes`:
    - `upgrade()` cleanly issues `DROP INDEX ix_news_articles_category_id;` and `DROP INDEX ix_news_articles_status;`.
    - `downgrade()` cleanly issues `CREATE INDEX ix_news_articles_status ...` and `CREATE INDEX ix_news_articles_category_id ...`.
  - Verified that composite indexes `ix_news_articles_category_published` on `(category_id, published_at)` and `ix_news_articles_status_published` on `(status, published_at)` remain active in both migration `0002` and model `__table_args__`.

### 5.5. Audit 5 — Classifier Determinism
- **Inspection:** Inspected [`backend/app/services/classifier_service.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/services/classifier_service.py).
- **Findings:**
  - Line 101 executes:
    ```python
    sorted_candidates = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best_category, max_score = sorted_candidates[0]
    ```
  - Sorting key `(-item[1], item[0])` orders by highest score first; on ties, category slugs are ordered alphabetically (`"business" < "environment" < "technology"`).
  - This eliminates dictionary iteration nondeterminism across Python versions or architectures.
  - The fallback mechanism (score < 2 defaulting to `"us"`) is explicitly documented in lines 79–83 and verified via `test_classifier_deterministic_tie_breaking` and `test_classifier_fallback_behavior`.

### 5.6. Audit 6 — Nginx Configuration
- **Inspection:** Inspected [`infrastructure/nginx/conf.d/metroscope.conf`](file:///c:/Users/Hasan/Documents/metroscope/infrastructure/nginx/conf.d/metroscope.conf).
- **Findings:**
  - Active server block (lines 12–63) listens on port 80 with explicit host routing:
    `server_name localhost 127.0.0.1 metroscope.news www.metroscope.news _;`
  - Commented SSL template block (lines 66–94) uses explicit server name `metroscope.news www.metroscope.news;` and certificate paths `/etc/letsencrypt/live/metroscope.news/`.
  - Zero unparsed `${...}` bash variable notations remain in the file.
  - Active traffic remains on HTTP port 80; SSL port 443 is not prematurely enabled.

### 5.7. Audit 8 — Phase 1 & Phase 2 Non-Regression & Scope Boundaries
- **Phase 1 Fixes Verified Intact:**
  - Nginx virtual host regex fix $\rightarrow$ INTACT.
  - `aiosqlite` dependency in `requirements.txt` $\rightarrow$ INTACT.
  - Dynamic DB health socket probe in `session.py` $\rightarrow$ INTACT.
  - Docker Compose memory limits totaling 1,408 MB $\rightarrow$ INTACT.
  - Next.js SPA client router navigation in `SiteHeader.tsx` and `search/page.tsx` $\rightarrow$ INTACT.
  - Automated security scans in `.github/workflows/ci.yml` $\rightarrow$ INTACT.
- **Strict Scope Boundaries Verified:**
  - No user registration, authentication, reader profiles, or dashboards exist.
  - No comments, likes, bookmarks, or social feeds exist.
  - No external social publishing to X or Facebook Pages is activated.
  - GDELT DOC 2.0 pipeline collects discovery metadata only; no full article body text or media files are scraped or stored.
  - UI remains the approved broadsheet design with Playfair Display typography, responsive breakpoints, and dark mode support.

---

## 6. Test Execution Matrix

All safe verification commands were executed directly in the current workspace.

| Test Category | Command Executed | Actual Exit Code | Result Details |
|---|---|:---:|---|
| **Backend Unit & Integration** | `cd backend; python -m pytest tests -v` | **0** | **29 passed, 1 warning in 1.12s** (0 failures). |
| **Frontend TypeScript** | `npm run typecheck --prefix frontend` | **0** | `tsc --noEmit` completed with **0 errors**. |
| **Frontend ESLint** | `npm run lint --prefix frontend` | **0** | `next lint` completed with **0 warnings, 0 errors**. |
| **Frontend Production Build** | `npm run build --prefix frontend` | **0** | All 9 routes compiled into optimized standalone/static bundles. |
| **Docker Compose Validation** | `docker compose config --quiet` | **0** | Configuration syntax and resource limits valid. |
| **Alembic Static DDL** | `cd backend; alembic upgrade head --sql` | **0** | Transactional DDL generated successfully through migration `0003`. |

---

## 7. Remaining Risks & Operational Notes

1. **Memory Budget on 2 GB RAM Production Server:** Total container memory allocation is constrained to 1,408 MB, leaving ~640 MB unreserved for Linux OS kernel and buffer cache. As documented in [`docs/ENVIRONMENT_SETUP.md`](file:///c:/Users/Hasan/Documents/metroscope/docs/ENVIRONMENT_SETUP.md), a 2 GB swapfile must be configured on the Ubuntu 24.04 LTS host upon deployment to protect against transient memory spikes during peak traffic.
2. **PostgreSQL Container Healthcheck Start Period:** In [`docker-compose.yml`](file:///c:/Users/Hasan/Documents/metroscope/docker-compose.yml), the database healthcheck has `start_period: 10s`. On initial deployment when creating database cluster files, PostgreSQL initialization may take 15–20s on slow EBS storage. The `retries: 5` setting provides sufficient margin (up to 50s total), but should be monitored during first boot.

---

## 8. Final Deliverable Summary

The full re-audit has verified that MetroScope Phase 2 and Phase 2.1 meet all architectural, functional, security, and quality requirements.

The repository is officially certified as **READY FOR PHASE 3**.

*Report compiled under strict read-only audit conditions.*
