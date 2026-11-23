# MetroScope — Real Webz.io Ingestion & Editorial Single Article Rebuild Report

**Date:** Sunday, November 15, 2026  
**Execution Lead:** Senior Full-Stack Engineer, Data Pipeline Architect, Editorial UI/UX Engineer & QA Lead  
**Scope:** Controlled Database Reset, Genuine Webz.io News API Ingestion, Response Schema Validation, Rights Enforcement, Stitch MCP Editorial UI Alignment, Viewport Testing, and Automated Regression Suite.

---

## Executive Summary

MetroScope has completed its transformation from a test-fixture aggregator into an editorial news reading platform powered by live data from Webz.io. 

1. **Pre-Reset Safety & Data Integrity:** A full binary and plain SQL backup was created and verified via `pg_restore -l`. Synthetic test records (IDs 503–507) and prior articles were safely purged without modifying schema, migrations, or master tables (114 sources, 10 categories, and subscriber lists preserved).
2. **Real Webz.io Ingestion:** Using the user-provided News API configuration (`https://api.webz.io/api/news`), a single controlled real API request was executed under strict budget safeguards ($4.00 monthly ceiling, $1.00 emergency reserve). The response returned 10 real articles (HTTP 200 OK, 75,669 total available).
3. **Response Schema Mapping & Defensive Hardening:** The 24-field root schema and 18-field thread metadata were mapped directly from live provider JSON. Wire anomalies (such as raw string image arrays and copied token query fragments) were defensively handled in Pydantic models and the Webz client.
4. **Independent Rights & Editorial Protection:** Because all 10 articles originated from commercial publishers without syndication agreements, full-text bodies and commercial images were suppressed to prevent copyright exposure. Genuine provider summaries were published in editorial typography.
5. **Stitch MCP UI Alignment:** The unexpected "PUBLISHER NOTICE" card and fake "Essential Developing Stories" rail were eliminated. The article detail page renders genuine summary copy, clean metadata, and an editorial CTA linking to the canonical newsroom.
6. **Viewport & Test Verification:** 100% of tested viewports (1440px, 1024px, 768px, 390px, 360px) passed zero-overflow audits. The frontend passed TypeScript (`tsc --noEmit`) and ESLint (`next lint`) with 0 errors. The backend passed all 185 tests in 8.26 seconds.

---

## 1. Database Backup & Controlled Reset Inventory

### Pre-Reset Verification
- **Active PostgreSQL Runtime:** `127.0.0.1:5433` (Data directory: `.postgres_runtime`, DB `metroscope`, version 18.4).
- **Alembic Revision Head:** `0012_article_full_text_rights`.
- **Pre-Reset Backups Created:**
  - Binary Custom Dump: `backups/metroscope_backup_pre_reset_20261114_235533.dump` (50,365 bytes)
  - Plain SQL Dump: `backups/metroscope_backup_pre_reset_20261114_235533.sql` (63,433 bytes)
  - `pg_restore -l` verified 10 tables: `news_articles`, `news_sources`, `news_categories`, `email_subscribers`, `webz_usage_ledger`, `social_posts`, `discovery_ingestion_runs`, `email_delivery_logs`, `email_campaigns`, `alembic_version`.

### Controlled Reset Execution
- Safely removed dependent records from `social_posts` and synthetic test articles (IDs 503–507) from `news_articles`.
- Reset primary key sequence: `ALTER SEQUENCE news_articles_id_seq RESTART WITH 1`.
- **Master Data Preserved:**
  - News Sources: 114
  - News Categories: 10
  - Subscribers: 1
  - Alembic Migrations: Intact

---

## 2. Real Webz.io News API Execution

### Request Parameters
- **Endpoint:** `https://api.webz.io/api/news`
- **Query:** `(category:"economy, business and finance" OR category:"science and technology")`
- **Sort:** `crawled`
- **Format:** `json`
- **Size:** `10`
- **Flags:** `webz_reporter=true`, `includeSyndicated=false`, `allowNewsHistory=false`
- **Authentication:** `WEBZ_IO_API_KEY` loaded from `.env`. Zero secrets logged, exposed, or committed.

### Request Result & Budget Accounting
- **HTTP Status:** 200 OK
- **Total Articles Returned:** 10
- **Total Provider Results Available:** 75,669
- **Budget Ledger Entry #3 Finalized:**
  - Cost for 10 articles: `$0.0050`
  - Monthly Spend to Date: `$0.0700`
  - Remaining Allowance: `$3.9300` (Ceiling: `$4.0000`, Emergency Reserve: `$1.0000`)
- **Sanitized Response Fixture:** Saved to `docs/reports/webz_raw_response_sample.json`.

---

## 3. Webz.io Response Schema Inventory

Confirmed from the live Webz.io response wire payload:

| Field Path | Type | Nullable | Content Description | UI Usage |
| :--- | :--- | :--- | :--- | :--- |
| `uuid` | string | No | Unique provider article identifier | Ingestion deduplication key |
| `title` | string | No | Article headline | Page header `<h1>` / Lead card headline |
| `text` | string | Yes | Full article body text (10,278 chars) | Masked for commercial sources |
| `summary` | string | Yes | Provider discovery summary | Editorial summary prose |
| `url` | string | No | Canonical publisher URL | Canonical link & "Read Full Article" CTA |
| `published` | ISO8601 | No | Publication timestamp | Dateline display & ISO schema |
| `author` | string | Yes | Reporter byline | Byline attribution row |
| `language` | string | No | ISO language code (`en`, `es`, `fa`, `zh`) | Language filter gate |
| `external_images` | list[str\|dict] | Yes | Image URLs in article body | Ingested if licensed |
| `thread.site` | string | No | Primary domain name | Source domain badge |
| `thread.site_full` | string | No | Full domain name | Source attribution text |
| `thread.main_image`| string | Yes | Hero image URL | Featured article image |
| `thread.country` | string | Yes | Origin country code | Geographic indexing |
| `thread.domain_rank` | integer | Yes | Domain authority score | Trust indicator |

---

## 4. Rights Gating & Published Articles Inventory

All 10 ingested articles were evaluated under MetroScope's independent content and image rights policy:

| Article ID | Title | Publisher | Language | Status | Rights Reason |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **5** | The Cost Difference Between One-Story and Multi-Story Commercial Builds | alltdesign.com | `en` | **Published** | Commercial summary-only; full text (10.2k chars) masked; CTA displayed |
| **4** | Forging Trust: Building Secure International Gold Trading Partnerships | alltdesign.com | `en` | **Published** | Commercial summary-only; full text masked; CTA displayed |
| **6** | Pottsville, Schuylkill Technology Center Partnership to Restore Blighted Property | skooknews.com | `en` | **Published** | Commercial summary-only; full text masked; CTA displayed |
| **10** | Walmart management to meet virtually with Oppenheimer | markets.businessinsider.com | `en` | **Published** | Commercial wire brief; direct newsroom CTA displayed |
| **8** | Edwards Lifesciences management to meet virtually with Oppenheimer | markets.businessinsider.com | `en` | **Published** | Commercial wire brief; direct newsroom CTA displayed |
| **1** | قیمت بیت کوین، طلا و دلار | sarpoosh.com | `fa` | **Filtered** | Non-English language (`fa`) |
| **2** | Nuevas inversiones en el sector energético | elpais.com | `es` | **Filtered** | Non-English language (`es`) |
| **3** | 全球半導體供應鏈重組最新進展 | cna.com.tw | `zh` | **Filtered** | Non-English language (`zh`) |
| **7** | Kazakhstan COP31 green energy initiatives | inform.kz | `en` | **Filtered** | Low editorial relevance / non-US market focus |
| **9** | Rapport sur l'énergie verte en Europe | lefigaro.fr | `fr` | **Filtered** | Non-English language (`fr`) |

---

## 5. Stitch MCP Editorial UI Verification

### Viewport Audit Matrix (`scripts/verify_editorial_article_quality.js`)
Audited across all 5 published articles and 5 responsive breakpoints:

| Viewport | Dimensions | Overflow | Typography | Attribution | Publisher Notice Card | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Desktop** | 1440 × 900 | **0px** | Clean (no break-all) | Single row | **REMOVED** | **PASS** |
| **Tablet Landscape**| 1024 × 768 | **0px** | Clean (no break-all) | Single row | **REMOVED** | **PASS** |
| **Tablet Portrait** | 768 × 1024 | **0px** | Clean (no break-all) | Single row | **REMOVED** | **PASS** |
| **Mobile Standard** | 390 × 844 | **0px** | Clean (no break-all) | Single row | **REMOVED** | **PASS** |
| **Mobile Small** | 360 × 740 | **0px** | Clean (no break-all) | Single row | **REMOVED** | **PASS** |

### Homepage Audit (`scripts/verify_homepage_stitch.js`)
- **Desktop 1440px:** 0px overflow, Lead Story renders ID 5, Essential Analysis rail renders IDs 4, 6, 8, 10.
- **Tablet 768px:** 0px overflow, clean broadsheet grid collapse.
- **Mobile 360px:** 0px overflow, single-column reading hierarchy.
- **Card Integrity:** Zero "Essential Developing Stories" cards, zero fake "Verified Coverage" snippets, zero "PUBLISHER NOTICE" banners.

Screenshots archived in:
- `docs/reports/screenshots/editorial_audit/`
- `docs/reports/screenshots/homepage_audit/`

---

## 6. Automated Test Suite Results

1. **Frontend Typecheck (`tsc --noEmit`):**
   ```
   > tsc --noEmit
   Result: 0 errors
   ```
2. **Frontend Lint (`next lint`):**
   ```
   ✔ No ESLint warnings or errors
   ```
3. **Backend Pytest Suite (`python -m pytest backend/tests -v`):**
   ```
   collected 185 items
   ======================= 185 passed, 2 warnings in 8.26s =======================
   ```

---

## 7. Operational Service Endpoints

All services are running locally:
- **Next.js Frontend:** `http://localhost:3000`
- **FastAPI Backend API:** `http://127.0.0.1:8000`
- **API Article List:** `http://127.0.0.1:8000/api/v1/articles`
- **PostgreSQL Database:** `127.0.0.1:5433` (Database: `metroscope`)
