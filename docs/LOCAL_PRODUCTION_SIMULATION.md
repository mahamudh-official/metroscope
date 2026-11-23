# MetroScope — Local Full Production Simulation Guide

**Document Version:** 2.0.0  
**Status:** Live & Production-Verified  
**Environment Target:** Local Full Production Simulation (Windows Native Cluster & Standalone Build)  
**Date:** November 14, 2026  
**Roles:** Senior Full-Stack Engineer, Data Engineer, News Content Pipeline Architect, Editorial UI/UX Engineer and QA Lead  

---

## 1. Executive Summary & Architecture

MetroScope is configured and running locally in a **100% production-equivalent runtime**. This simulation accurately reproduces production execution, security settings, error handling, background schedules, and persistent data storage without deploying to AWS.

### Production Parity Architecture

```
                                  [ Browser / Client ]
                                           │
                                  HTTP Port 3000
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │  Next.js 14 Standalone Production Server    │
                    │  (server.js, pre-rendered static assets)     │
                    │  Internal Proxy Rewrites: /api/v1/* ─────────┼───────┐
                    └──────────────────────────────────────────────┘       │
                                                                           │
                                  HTTP Port 8000                           │
                                           │                               │
                                           ▼                               ▼
                    ┌────────────────────────────────────────────────────────┐
                    │        FastAPI Production Application (Uvicorn)        │
                    │  - DEBUG=false, ENVIRONMENT=production                 │
                    │  - Strict TrustedHost & CORS origin enforcement        │
                    │  - Sanitized public errors (no stack trace exposure)   │
                    │  - Security Headers (nosniff, SAMEORIGIN)              │
                    └──────────────┬────────────────────────┬────────────────┘
                                   │                        │
                                   ▼                        ▼
                    ┌─────────────────────────┐  ┌───────────────────────────┐
                    │  PostgreSQL Cluster     │  │   APScheduler Worker      │
                    │  - Port 5433 (Native)   │  │   - 08:00 Sports (Dhaka)  │
                    │  - .postgres_runtime/   │  │   - 20:00 Business (Dhaka)│
                    │  - Head: 0012 Migration │  │   - Social Publisher (Dry)│
                    │  - 500 Articles, 114 Src│  │   - Daily Newsletter (Dry)│
                    └─────────────────────────┘  └───────────────────────────┘
```

---

## 2. One-Command Service Orchestration

### Reliable Startup Command
To start all services in the background (PostgreSQL, Backend API, APScheduler News Worker, and Next.js Standalone Frontend):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_start.ps1
```

*For foreground monitoring mode where the terminal stays attached:*
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_start.ps1 -KeepAlive
```

### Reliable Shutdown Command
To gracefully terminate all running services without losing database records or uncommitted files:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_stop.ps1
```

### Real-Time Service Status
To inspect the health, process IDs, and operational metrics of all services:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_status.ps1
```

### Live Log Streaming
To inspect or tail live logs across all services:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\local_logs.ps1
```

---

## 3. Working Local Endpoints & URLs

### Web Applications & Public Pages
| Service / Page | Local URL | Description |
| :--- | :--- | :--- |
| **Homepage** | `http://localhost:3000/` | Production Homepage, Hero, Wire feed, Category grids |
| **Article Details** | `http://localhost:3000/article/[slug]` | Full article reader with publisher source attribution |
| **Category Pages** | `http://localhost:3000/category/[slug]` | All 10 active categories (see Section 4) |
| **Search Engine** | `http://localhost:3000/search?q=[query]` | Client-side search proxied to `/api/v1/articles` |
| **About Us** | `http://localhost:3000/about` | Editorial mission, journalistic standards, platform ethics |
| **Contact & Inquiries** | `http://localhost:3000/contact` | Editorial desks, press contacts, feedback form |
| **Privacy Policy** | `http://localhost:3000/privacy` | Privacy policy & data protection practices |
| **Terms of Service** | `http://localhost:3000/terms` | Terms of service, copyright notices, attribution rules |
| **RSS Feed** | `http://localhost:3000/rss.xml` | XML RSS 2.0 discovery feed for aggregators |
| **Atom Feed** | `http://localhost:3000/feed.xml` | XML Atom syndication feed |
| **Sitemap** | `http://localhost:3000/sitemap.xml` | Canonical XML sitemap for search indexers |
| **Robots Exclusion** | `http://localhost:3000/robots.txt` | Crawler directives & sitemap location |
| **Newsletter Verify** | `http://localhost:3000/verify-subscription?token=...` | Double opt-in activation landing page |
| **Newsletter Unsub** | `http://localhost:3000/unsubscribe?token=...` | Instant single-click unsubscribe landing page |

### API & Health Check Probes
| Probe Endpoint | Full Local URL | Purpose / Expected Response |
| :--- | :--- | :--- |
| **Primary Health Probe** | `http://127.0.0.1:8000/health` | HTTP 200 `{"status":"ok","database_connected":true}` |
| **K8s/Docker Liveness** | `http://127.0.0.1:8000/health/live` | HTTP 200 `{"status":"alive"}` |
| **K8s/Docker Readiness** | `http://127.0.0.1:8000/health/ready` | HTTP 200 `{"status":"ready"}` |
| **Operational Metrics** | `http://127.0.0.1:8000/health/metrics` | HTTP 200 `total_articles`, `active_subscribers`, dry-run flags |
| **API Version Health** | `http://127.0.0.1:8000/api/v1/health` | HTTP 200 API v1 health alias |
| **API Articles List** | `http://127.0.0.1:8000/api/v1/articles` | Paginated article list with filtering |
| **API Categories** | `http://127.0.0.1:8000/api/v1/categories` | Returns all 10 active news categories |
| **API Interactive Docs**| `http://127.0.0.1:8000/docs` | Returns HTTP 404 in production mode (`DEBUG=false`) |

---

## 4. Category Routing & Alignment

All 10 active database categories are accessible via clean URLs and navigation bars:

1. **U.S. News:** `http://localhost:3000/category/us` (Legacy alias `/category/us-news` automatically redirects)
2. **World News:** `http://localhost:3000/category/world`
3. **Politics:** `http://localhost:3000/category/politics`
4. **Business & Economy:** `http://localhost:3000/category/business` (Legacy alias `/category/markets` automatically redirects)
5. **Technology:** `http://localhost:3000/category/technology`
6. **Science:** `http://localhost:3000/category/science`
7. **Health:** `http://localhost:3000/category/health`
8. **Environment & Climate:** `http://localhost:3000/category/environment`
9. **Sports:** `http://localhost:3000/category/sports`
10. **Entertainment:** `http://localhost:3000/category/entertainment` (Legacy alias `/category/culture` automatically redirects)

---

## 5. External Integrations & Dry-Run Modes

### Webz.io News Ingestion
- **Configuration:** Set `WEBZ_IO_API_KEY` in `.env`.
- **Budget Protection:** Enforced by `BudgetProtectionService` ($4.00 collection ceiling, $1.00 emergency reserve).
- **Collection Schedule:**
  - Morning Beat (Sports): 08:00 Asia/Dhaka (02:00 UTC)
  - Evening Beat (Business): 20:00 Asia/Dhaka (14:00 UTC)
- **Controlled Manual Verification:**
  ```powershell
  python backend/scripts/smoke_test_webz.py --confirm-cost
  ```
  *(Requires valid `WEBZ_IO_API_KEY` in `.env`)*

### Email & Newsletter Delivery (Local Capture Mode)
- **Safe Local Testing Mode:** `EMAIL_DRY_RUN=true` (Default)
- **Message Capture:** Outgoing emails are captured to `logs/captured_emails.log` with label `LOCAL_CAPTURE_NOT_DELIVERED`.
- **How to Test Subscription & Verification:**
  1. Open `http://localhost:3000/` and enter your test email in the newsletter form.
  2. Inspect `logs/captured_emails.log` for the verification link.
  3. Click or navigate to `http://localhost:3000/verify-subscription?token=<TOKEN>` in your browser.
  4. Verify the UI transitions to `"Subscription Confirmed"`.
- **How to Switch to Real SMTP Mailbox:**
  Set in `.env`:
  ```ini
  EMAIL_DRY_RUN=false
  SMTP_HOST=smtp.sendgrid.net  # or mail.smtp2go.com
  SMTP_PORT=587
  SMTP_USERNAME=apikey
  SMTP_PASSWORD=your_real_smtp_password
  SMTP_USE_TLS=true
  ```

### Social Media Publishing (Facebook & X)
- **Safe Local Testing Mode:** `SOCIAL_DRY_RUN=true` (Default)
- **Post Safeguard:** Meta Graph API and X API v2 network requests are simulated. Payloads, character count validations (280 characters for X, title + clean link for Facebook), and simulated post IDs are written to `logs/worker.log`.
- **Public Protection:** Never set `SOCIAL_DRY_RUN=false` without approved, dedicated test accounts.

---

## 6. Logs & Diagnostics

All application logs are persisted to the `logs/` directory:

| Log File | Component | What to Look For |
| :--- | :--- | :--- |
| `logs/postgres.log` | PostgreSQL Cluster | Database checkpoints, connection counts, WAL activity |
| `logs/backend.log` | FastAPI API Server | HTTP request access logs, response times, status codes |
| `logs/backend.err.log` | FastAPI Error Output | Unhandled exceptions, configuration audit warnings |
| `logs/worker.log` | APScheduler Worker | Scheduled job triggers, Webz collection runs, social dry-runs |
| `logs/frontend.log` | Next.js Standalone | SSR render events, client proxy rewrites, static caching |
| `logs/captured_emails.log` | Local Email Capture | Verification tokens, unsubscribe tokens, HTML/text bodies |

---

## 7. Automatic Recovery & Persistence After PC Restart

1. **Persistent Data:** The PostgreSQL data directory `.postgres_runtime` is persistent and untouched by reboots or script restarts.
2. **Crash Recovery:** `scripts/local_start.ps1` detects stale `postmaster.pid` files after unexpected shutdowns, performs automatic WAL replay via PostgreSQL, and verifies connectivity via `pg_isready.exe`.
3. **Restoring Services:** After restarting your PC, simply run:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\local_start.ps1
   ```
   All published articles, sources, and subscriber states will be immediately available.

---

## 8. Full Article Body Rendering & Content Licensing Engine

### Content Pipeline & Database Architecture
- **Webz.io Field Differentiation:**
  - `post.text`: Extracted as raw root-level full article body text and persisted in `news_articles.full_text` (nullable Text).
  - `post.summary`: Stored as `news_articles.description` for discovery and permitted summaries.
  - `post.thread.text`: Preserved independently; never confused with primary article body.
- **Database Migration:** `0012_article_full_text_rights` applied safely without data loss, adding `full_text` (Text, nullable) and `content_display_authorized` (Boolean, default `false`, not null).
- **Licensing & Publication Rights (`ContentRightsService`):**
  - Evaluates publisher domains against statutory public domain status (e.g., U.S. Federal government works under 17 U.S.C. § 105 like `nasa.gov`, `cdc.gov`, `noaa.gov`, `state.gov`) or verified syndication contracts.
  - Commercial copyrighted publishers default to `content_display_authorized = false`.
  - Crawler directives (`ai_allow: true`) and external Creative Commons (CC BY) links are strictly disregarded and never treated as republication permission.
- **Article Detail Page UI (`frontend/src/app/article/[slug]/page.tsx`):**
  - **Redundant Attribution Box Removed:** Completely removed the separate "Original Reporting by [Publisher]" box and duplicate source URL display.
  - **Attribution Row Kept:** Headline attribution row displays clean `"Originally published by [Publisher]"` with external link.
  - **Authorized Full Text Display:** Displays full article body with paragraph boundaries and natural word wrapping (`[overflow-wrap:break-word] [word-break:normal]`) and full Unicode preservation.
  - **Permitted Summary Fallback:** When full text is missing or unauthorized, displays the permitted summary with direct external publisher link without fabricating paragraphs.
- **Verification Matrix (`scripts/verify_full_text_matrix.py`):**
  - Verified English full text authorized (`test-auth-english-fulltext`).
  - Verified non-English Unicode text authorized (`test-auth-unicode-bangla`).
  - Verified commercial proprietary full text masking (`test-unauth-commercial-masked`).
  - Verified summary-only wire reports (`test-summary-only-wire`).
  - Verified headline-only notice fallback (`test-neither-field-flash`).

---

## 9. Global Editorial Article Quality, Image Pipeline & Quality Gate

### 1. Typography & Natural Word Wrapping Fix
- **Root Cause:** A prior regression test rule required `break-all` in article page markup, which was inadvertently applied to normal article prose. This caused CSS `word-break: break-all`, breaking ordinary English and Unicode words mid-word across browsers.
- **Resolution:**
  - Applied `[overflow-wrap:break-word] [word-break:normal]` to all article body paragraphs and summary ledes.
  - Placed `break-all` specifically on the canonical source link anchor (`<a href={canonicalUrl} className="... break-all">`) to prevent long URLs from overflowing viewports without affecting prose text.
  - Fully supports English and complex Unicode scripts (Bangla, Macedonian, Arabic, etc.) with natural word boundaries.

### 2. Article Hero Image Pipeline
- **Root Cause:** Over 270 articles in the database possessed valid Webz.io CDN image URLs, but the article detail template lacked an image rendering component.
- **Resolution:**
  - **Webz Parser Cascade (`extract_primary_image`):** Evaluates `post.thread.main_image`, then `post.internal_images`, then `post.external_images` in priority order. Validates URLs with strict scheme checking (`http/https`) and rejects tracking pixels (`pixel.gif`, `1x1`, `spacer.gif`) and private network IPs.
  - **Client Component (`ArticleHeroImage.tsx`):** Renders a responsive 16:9 hero image using Next.js `Image` with `unoptimized={true}` and `referrerPolicy="no-referrer"` to eliminate publisher CDN hotlink/user-agent blocks.
  - **Zero-Glitch Fallback:** Implements an `onError` listener that gracefully unmounts the component and renders `null` if remote CDN images fail to load or return 403/404, guaranteeing that broken image placeholders or broken icons are never displayed to users.

### 3. Unified Editorial Presentation & Summary Hierarchy
- Standardized single editorial template across all articles:
  1. Breadcrumb navigation (`Front Page / Category / Headline`).
  2. Category badge and publication date.
  3. Large editorial serif headline (`text-3xl sm:text-4xl md:text-5xl`).
  4. Single publisher attribution row (`"Originally published by [Publisher]"`).
  5. Responsive hero image (when a valid, loadable image exists).
  6. Prominent summary lede above body with gold border (`border-secondary`) when genuine.
  7. Full article body (when authorized) or clean summary fallback (when unauthorized).
  8. Related editorial coverage grid.
- Completely removed redundant "Original Reporting by..." cards, duplicate publisher descriptions, and repeated source URLs.

### 4. Editorial Quality Gate (`ArticleEditorialValidationService`)
- Added comprehensive pre-publication validation in `backend/app/services/article_validation_service.py` integrated into `WebzIngestionService`:
  - **Headline Gate:** Validates length (10–300 chars), rejects raw URLs, file extensions, and generic error headlines.
  - **URL & Domain Gate:** Validates canonical URLs and rejects private/loopback/IP-only hosts.
  - **Publication Date Gate:** Rejects future dates or timestamps older than 30 days.
  - **Summary Gate:** Rejects duplicate headlines, boilerplate cookie/paywall notices, and placeholders.
  - **Body Content Gate:** Rejects empty or corrupt bodies; verifies valid paragraph structure.
  - **Image Gate:** Validates image URL format and dimensions.

### 5. Verification Across 5 Responsive Viewports
Headless Chrome Puppeteer verification (`scripts/verify_editorial_article_quality.js`) executed across 5 standard device viewports:
- **1440px (Desktop):** 0px horizontal overflow, full hero image displayed, clean single attribution row.
- **1024px (Tablet Landscape):** 0px horizontal overflow, broadsheet typography balanced.
- **768px (Tablet Portrait):** 0px horizontal overflow, responsive hero image scaled seamlessly.
- **390px (Mobile - iPhone 12/13/14/15):** 0px horizontal overflow, zero mid-word breaking, clean lede presentation.
- **360px (Mobile - Android Compact):** 0px horizontal overflow, natural word wrapping preserved.
- **Audit Screenshots:** Persisted in `docs/reports/screenshots/editorial_audit/`.

---

## 10. Complete Single-Page News Platform Rebuild & Dataset Reset (Phases 1–9)

### 10.1 Database Backup & Controlled Cleanup (Phase 1)
- **Active PostgreSQL Runtime:**
  - Cluster directory: `.postgres_runtime`
  - Host/Port: `127.0.0.1:5433`
  - Database: `metroscope`
  - Alembic Head Revision: `0012_article_full_text_rights`
- **Backup Verification Before Cleanup:**
  - Custom format archive: `backups/metroscope_backup_pre_cleanup_20261114_052203Z.dump` (165,324 bytes).
  - Plain SQL dump: `backups/metroscope_backup_pre_cleanup_20261114_052203Z.sql` (442,979 bytes).
  - Inspection with `pg_restore.exe -l` confirmed 117 table, index, sequence, and constraint definitions.
- **Before / After Inventory:**
  - **Before Cleanup:** `news_articles`: 506 (500 published, 6 filtered; IDs 1–507), `social_posts`: 8, `news_sources`: 114, `news_categories`: 10, `email_subscribers`: 1, `discovery_ingestion_runs`: 23.
  - **Controlled Deletion:** Safely cleared 8 dependent `social_posts` and 506 `news_articles` via foreign-key-safe atomic transaction. Synthetic test records IDs 503–507 and old unverified articles were completely purged.
  - **Preserved Master Data:** All 114 news sources, 10 categories, 1 subscriber, 23 ingestion runs, and Alembic version history remained 100% intact.
  - **Sequence Reset:** `news_articles_id_seq` and `social_posts_id_seq` reset safely to 1.
  - **Verified Matrix Seed:** 5 target test matrix records (IDs 1–5) seeded for rigorous acceptance verification.

### 10.2 Webz.io JSON Schema Field Mapping & Ingestion Validation (Phase 2 & 5)
Strictly adheres to actual Webz.io API responses without inventing field names:
- `thread.title`: Normalized headline.
- `thread.main_image`: Candidate primary article image.
- `post.text`: Raw full article body text (persisted as `news_articles.full_text`). Never substituted with summary or thread text.
- `post.summary`: Brief discovery summary (persisted as `news_articles.description`).
- `post.thread.text`: Thread context, preserved separately.
- `language`: BCP-47 / ISO language code.
- `author`: Authentic author name (defaults to Publisher attribution if null).
- `url`: Canonical article URL.
- `published`: ISO 8601 publication timestamp.
- `site` / `site_full`: Source domain identification.
- `internal_images` / `external_images`: Array of candidate inline images with captions, credits, and dimensions.
- **Validation Rules (`ArticleEditorialValidationService`):**
  - Structural schema integrity and presence of title and source.
  - Valid http/https canonical URL with rejection of private/loopback RFC 1918 IPs.
  - Publication timestamp freshness (rejects future dates or stories > 30 days old).
  - Minimum content length and meaningful paragraph structure.
  - Headline/body mismatch and near-duplicate story rejection.
  - Rejection of navigation menus, cookie walls, paywalls, and boilerplate disclaimers.
  - Rejection of tracking pixels (`pixel.gif`, `1x1`, `spacer.gif`) and zero-dimension images.
  - Stub article rejection: records lacking both genuine summary and body are rejected.

### 10.3 Content & Image Rights Policy Engine (Phase 3)
Independent, tripartite authorization decisions executed by `ContentRightsService`:
1. **Full Article Text (`evaluate_full_text_rights`):**
   - Statutory Public Domain: Restricted to verified U.S. Federal Government works under 17 U.S.C. § 105 (`nasa.gov`, `cdc.gov`, `noaa.gov`, `whitehouse.gov`, `state.gov`, `loc.gov`, `defense.gov`, `nih.gov`, `epa.gov`, `usgs.gov`).
   - Broad `.gov` wildcard **completely removed** to prevent improper republication of state, municipal, or foreign government proprietary works.
   - Commercial Publishers: Default to `content_display_authorized = false`. Full text is masked (`full_text = None` in public API) and only permitted discovery summaries are served with canonical publisher links.
   - Directives like `ai_allow: true` or external CC BY links are strictly rejected as republication permissions.
2. **Hero Image Rights (`evaluate_hero_image_rights`):**
   - Authorized only for verified public domain institutions.
   - Wire Photo Detection: Specifically inspects image metadata and captions for third-party commercial wire services (Getty Images, Associated Press, Reuters, AFP, Bloomberg) embedded on government pages and rejects them.
   - Unauthorized hero images result in `image_url = None` in public API; frontend renders an elegant image-free editorial layout.
3. **Inline Image Rights (`evaluate_inline_image_rights`):**
   - Evaluated independently from the hero image. Inline images from commercial wires are withheld, while authentic institutional graphics are authorized.

### 10.4 Single-Page Broadsheet Reading Experience (Phase 4 & 6)
Inspired by the Prothom Alo broadsheet newspaper article reading experience, translated into MetroScope's original Navy & Gold visual identity (`frontend/src/app/article/[slug]/page.tsx`):
- **Breadcrumb Navigation:** `Front Page / Category / Headline`.
- **Editorial Masthead:** Category badge, publication timestamp, reading time estimate, breaking/trending badges.
- **Large Serif Headline:** Broadsheet serif typography (`font-serif leading-[1.2]`) with natural word wrapping (`[overflow-wrap:break-word] [word-break:normal]`).
- **Single Publisher Attribution Row:** Clean `"By [Author] · Originally published by [Publisher]"` with canonical link (`break-all` restricted to link anchor to prevent URL overflow).
- **Hero Image with Caption & Credit:** `ArticleHeroImage.tsx` with responsive 16:9 container, italicized caption, uppercase credit badge, and silent unmount on CDN failure.
- **Bold Summary Lede:** Displayed above body only when an authentic summary exists; never fabricated.
- **Continuous Reading Column:** `max-w-3xl` reading column with generous line height (`leading-[1.8]`), paragraph margins, subheading hierarchy (`h2`/`h3`), styled blockquotes with gold border, and responsive inline images.
- **Summary-Only Commercial Fallback:** Clear, dignified call-to-action card (`"Read Full Article at [Publisher]"`) for commercial articles without full-text licensing.
- **Related Editorial Coverage:** Curated related stories from the same category.

### 10.5 5-Viewport Responsive Audit & Test Results (Phase 8)
- **1440px Desktop:** 0px horizontal overflow, full hero image displayed, reading column centered.
- **1024px Laptop:** 0px horizontal overflow, balanced typography and sidebar.
- **768px Tablet:** 0px horizontal overflow, responsive hero image and readable typography.
- **390px Mobile:** 0px horizontal overflow, natural word wrapping without mid-word breaks, comfortable touch targets.
- **360px Small Mobile:** 0px horizontal overflow, broadsheet layout preserved without clipping.
- **Audit Screenshots:** Saved under `docs/reports/screenshots/editorial_audit/`:
  - `desktop_1440px_test-auth-english-fulltext.png`
  - `mobile_360px_test-auth-english-fulltext.png`
  - `desktop_1440px_test-auth-unicode-bangla.png`
  - `mobile_360px_test-auth-unicode-bangla.png`
  - `desktop_1440px_test-unauth-commercial-masked.png`
  - `mobile_360px_test-unauth-commercial-masked.png`
  - `desktop_1440px_test-summary-only-wire.png`
  - `mobile_360px_test-summary-only-wire.png`
- **Automated Verification:**
  - Full backend pytest suite: **185 passed** in 9.09s (`pytest backend/tests -v`).
  - Frontend typecheck: **0 errors** (`npm --prefix frontend run typecheck`).
  - Frontend lint: **0 warnings, 0 errors** (`npm --prefix frontend run lint`).
  - Frontend production build: **Exit code 0** (`npm --prefix frontend run build`).
  - Endpoint audit: **100% HTTP 200 OK** across health, categories, feeds, search, and articles (`scripts/verify_all_endpoints.py`).
  - Puppeteer functional test: **12/12 routes passed** with 0 console errors and 0 failed requests (`scripts/browser_functional_test.js`).


