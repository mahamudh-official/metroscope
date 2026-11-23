# MetroScope — Complete Public-Facing Website & Production Readiness Audit (Phase A)

**Audit Date:** November 12, 2026  
**Role:** Senior Full-Stack Engineer, Production Architect, UI/UX Engineer, QA Engineer & Digital News Platform Specialist  
**Audit Scope:** Full read-only inspection of Frontend (Next.js 14 App Router, TypeScript, Tailwind CSS), Backend (FastAPI, SQLAlchemy 2, Alembic, Webz.io Integration), PostgreSQL Database (`.postgres_runtime`, 501 articles, 114 sources, 10 categories), SEO/Structured Data, and Security/Production Configuration.  
**Application Code Modified During Audit:** None (Strict Read-Only Phase A Inspection).

---

## 1. Executive Summary

MetroScope has a solid architectural foundation (FastAPI, PostgreSQL, Next.js 14 App Router, APScheduler, Webz.io integration with budget protection, social publishing, and double opt-in email newsletters). However, a comprehensive code, database, CSS compilation, test suite, and visual inspection revealed **20 concrete findings** (**5 Critical, 7 High, 5 Medium, 3 Low**) that currently prevent the platform from looking and behaving like a trustworthy, production-ready digital news publication.

### Key Highlights of What Was Found:
1. **Database Schema Drift & Local Startup Script Bug (CRIT-01):** The active PostgreSQL database (`.postgres_runtime`) is at migration `0008_email_newsletter`, missing three newer migrations (`0009_webz_io_migration`, `0010_webz_field_expansion`, `493f6e6a0c63`). Why? Because `scripts/local_start.ps1` sets `$ErrorActionPreference = 'Stop'` and runs `$migOutput = python -m alembic upgrade head 2>&1`—in PowerShell, Alembic's `INFO` log output on `stderr` triggers an immediate exception before migrations apply. As a result, querying `/api/v1/articles` against `.postgres_runtime` fails with HTTP 500 (`UndefinedColumnError: column news_articles.uuid does not exist`).
2. **Broken Main Navigation Links Returning HTTP 404 (CRIT-02):** Every page's header (`MainNavigation.tsx`, `SiteHeader.tsx`) and footer (`SiteFooter.tsx`) link to `/category/culture` and `/category/opinion`, neither of which exists in `CATEGORY_NAMES` (`frontend/src/app/category/[slug]/page.tsx`) or the database. Clicking either link returns a 404 page, while four active database categories (`health`, `environment`, `sports`, `entertainment`) are hidden from main navigation.
3. **Broken Client-Side Search in Standalone Mode (CRIT-03):** `frontend/src/app/search/page.tsx` calls `fetch("/api/v1/articles?q=...")` directly instead of using `fetchArticles()` from `src/lib/api.ts`, and `next.config.mjs` defines no `/api/v1` rewrite proxy. Without Nginx in front, every search hits Next.js, receives 404, is silently caught, and falsely displays `"No matching articles found"`.
4. **Fabricated Headlines in Homepage Empty State (CRIT-04):** When the wire feed array is empty, `frontend/src/app/page.tsx` renders three invented news headlines attributed to `"MetroScope Wire • Premier Publisher"`, violating Constraint #12 and Section 4.2.
5. **Unmapped Tailwind Theme Tokens Breaking Contrast & Dark Mode (CRIT-05):** `globals.css` defines `--background`, `--foreground`, `--border`, and `--muted`, and components use `text-foreground`, `text-muted`, `border-border`, `divide-border`, and `bg-background`. However, `tailwind.config.ts` never registered those color keys. Zero CSS rules are generated for `.text-muted` or `.border-border`, breaking visual hierarchy in light mode and leaving bright white/gray borders and an unreadable dark-navy logo in dark mode.
6. **Public API Schema & Content Leakage (HIGH-01 to HIGH-07):**
   - `ArticleDetail` and `ArticleListItem` expose internal fields (`uuid`, `canonical_url_hash`, `original_url`, `trust_indicators`, `filter_reason`, `quality_score`, `cluster_id`, `webz_categories`, `sentiment`, `status`, `discovered_at`, `created_at`).
   - 136 database articles contain a fabricated placeholder summary with external-site instructions: `"Comprehensive wire coverage and primary reporting. Access the original publication for full context."`
   - 105 of 114 sources in `news_sources` use raw capitalized domain strings (e.g., `550thezone.iheart.com`, `Deperu.com`, `Pt.euronews.com`) as their display name and have `country='US'` forced by a legacy column `server_default`.
   - Several database records are non-article utility pages (`"IOPscience terms & conditions"`, `"Accessibility statement"`, `"About IOPscience"`, `"Subject collections"`), single-word fragments (`"🏀 Kaufman"`), or non-English posts marked `language='en'`.
   - `/about` exposes internal server hardware and framework specs (`"2 vCPU, 2 GB RAM"`, `"FastAPI, PostgreSQL, Next.js, and APScheduler"`, `"modular monolith"`).
   - `/contact` fakes message submission (`"Submit Transmission"` -> `"Message Transmitted"`) in local React state while discarding user input.

---

## 2. Summary Matrix of All Audit Findings

| ID | Severity | Title | Primary Location(s) | Affected Domains |
| :--- | :--- | :--- | :--- | :--- |
| **CRIT-01** | **Critical** | Unapplied DB migrations (`0009`–`493f6e6a0c63`) & PowerShell `2>&1` bug causing HTTP 500 on `/api/v1/articles` | `scripts/local_start.ps1`, `.postgres_runtime`, `backend/app/models/article.py` | Backend, DB, Frontend |
| **CRIT-02** | **Critical** | Dead navigation links (`/category/culture`, `/category/opinion`) returning 404 & missing active categories | `MainNavigation.tsx`, `SiteHeader.tsx`, `SiteFooter.tsx`, `category/[slug]/page.tsx` | Frontend, UX, SEO |
| **CRIT-03** | **Critical** | Search page hardcodes `/api/v1/articles` without `lib/api.ts` or Next.js rewrite, failing in standalone mode | `frontend/src/app/search/page.tsx`, `frontend/next.config.mjs` | Frontend, UX |
| **CRIT-04** | **Critical** | Fabricated news headlines and fake `"MetroScope Wire"` attribution hardcoded in Homepage empty state | `frontend/src/app/page.tsx` (lines 189–220) | Frontend, Content |
| **CRIT-05** | **Critical** | Missing Tailwind color mappings (`foreground`, `muted`, `border`, `background`) & unreadable dark-mode logo | `frontend/tailwind.config.ts`, `frontend/src/app/globals.css`, `SiteHeader.tsx` | Frontend, Brand, A11y |
| **HIGH-01** | **High** | Public API schemas expose internal provider & pipeline fields (`uuid`, `canonical_url_hash`, `trust_indicators`, `webz_categories`, `filter_reason`, `quality_score`, `cluster_id`) | `backend/app/schemas/article.py`, `frontend/src/lib/api.ts` | Backend, Security, Content |
| **HIGH-02** | **High** | 136 database articles display fabricated placeholder summary & external-website instructions | PostgreSQL `news_articles` (IDs 1–136), `article/[slug]/page.tsx` | Content, Backend, Frontend |
| **HIGH-03** | **High** | Public "About Us" page exposes internal EC2 hardware specs (`2 vCPU, 2 GB RAM`) and backend stack details | `frontend/src/app/about/page.tsx` (lines 27–62) | Frontend, Content, Security |
| **HIGH-04** | **High** | Unverified third-party article images exposed in OpenGraph, Twitter Cards, and Schema.org JSON-LD | `frontend/src/app/article/[slug]/page.tsx` (lines 44, 75), `frontend/src/lib/seo.ts` | SEO, Copyright |
| **HIGH-05** | **High** | Contact page simulates `"Message Transmitted"` in client state while discarding messages | `frontend/src/app/contact/page.tsx` (lines 11–16, 45, 54–61, 121) | Frontend, UX |
| **HIGH-06** | **High** | Non-article utility pages, foreign-language posts, truncated headlines in DB & missing quality gate in `WebzIngestionService` | `backend/app/services/webz_ingestion_service.py`, `backend/app/integrations/webz/parser.py`, DB `news_articles` | Backend, Content |
| **HIGH-07** | **High** | Raw domain strings used as publisher display names on 105/114 sources & `server_default='US'` country distortion | DB `news_sources`, `source_repository.py`, `webz/parser.py`, migration `493f6e6a0c63` | Backend, Content, Frontend |
| **MED-01** | **Medium** | Scraper/pipeline jargon (`"News Discovery"`, `"Wire Record"`, `"Real-time Normalized"`, `"Sector Intelligence"`) and verbose disclaimer box across UI | `article/[slug]/page.tsx`, `category/[slug]/page.tsx`, `search/page.tsx`, `not-found.tsx` | Frontend, Content, UX |
| **MED-02** | **Medium** | Duplicate category routes (`/category/us` vs `/category/us-news`, `/category/business` vs `/category/markets`) with conflicting canonical URLs | `frontend/src/app/category/[slug]/page.tsx`, `MainNavigation.tsx` | SEO, Frontend |
| **MED-03** | **Medium** | Missing pagination on Category pages and Search page (hardcoded `page=1`) | `frontend/src/app/category/[slug]/page.tsx`, `frontend/src/app/search/page.tsx` | Frontend, UX, SEO |
| **MED-04** | **Medium** | Schema.org `NewsArticle` JSON-LD misattributes third-party reporting to MetroScope without `isBasedOn` / `sameAs` | `frontend/src/lib/seo.ts` (lines 91–139), `article/[slug]/page.tsx` | SEO, Content |
| **MED-05** | **Medium** | 2 failing pytest regression tests (`test_phase10_ux_regression.py`, `test_phase12_content_expansion.py`) & scheduler job naming mismatch | `backend/tests/test_phase10_ux_regression.py`, `backend/tests/test_phase12_content_expansion.py`, `webz/client.py`, `workers/jobs.py` | Backend, QA |
| **LOW-01** | **Low** | Newsletter Verify & Unsubscribe pages use hardcoded `bg-white`/`text-gray-900` and broken dark-mode `bg-primary text-white` buttons | `frontend/src/app/verify-subscription/page.tsx`, `frontend/src/app/unsubscribe/page.tsx` | Frontend, Brand, A11y |
| **LOW-02** | **Low** | Untracked review dump files (`metroscope_review_bundle.txt`, `metroscope_review_supplement.txt`) in workspace root | Root directory, `.gitignore` | Security, Hygiene |
| **LOW-03** | **Low** | Static `"Breaking Wire"` ticker banner on every page & `"Discovered story"` phrasing in RSS feed | `frontend/src/components/SiteHeader.tsx`, `frontend/src/app/feed.xml/route.ts` | Frontend, Content |

---

## 3. Detailed Audit Findings

### CRIT-01: Unapplied Database Migrations (`0009`, `0010`, `493f6e6a0c63`) & PowerShell `2>&1` Startup Bug Causing HTTP 500 on All Article Queries
- **Location / File / Component:**
  - `scripts/local_start.ps1` (lines 10, 122–129)
  - PostgreSQL `.postgres_runtime` (`alembic_version` table and `news_articles` table)
  - `backend/app/models/article.py` (lines 57–91, 108)
  - `backend/alembic/versions/20261110_0009_webz_io_migration.py`
  - `backend/alembic/versions/20261111_0010_webz_field_expansion.py`
  - `backend/alembic/versions/20261111_1302_493f6e6a0c63_allow_unknown_article_and_source_.py`
- **Actual Problem:**
  - Direct inspection of `.postgres_runtime` on port 5433 showed `SELECT version_num FROM alembic_version` is `['0008_email_newsletter']`, and `news_articles` only has 22 columns (missing `uuid`, `author`, `topics`, `trust_indicators`, `image_metadata`, `publisher_name`, `crawled_at`, `sentiment`, `webz_categories`).
  - Calling `list_articles()` or `get_article_by_slug()` raises `sqlalchemy.exc.ProgrammingError: UndefinedColumnError: column news_articles.uuid does not exist`.
  - In `scripts/local_start.ps1`, `$ErrorActionPreference = 'Stop'` (line 10) causes `$migOutput = python -m alembic upgrade head 2>&1` (line 124) to throw a terminating PowerShell `NativeCommandError` on the very first `INFO [alembic.runtime.migration]` line written to `stderr`, aborting `alembic upgrade head` before any migration executes.
- **Severity:** **Critical**
- **Affects:** Backend, Database, Frontend, Content
- **Why It Matters:** When the backend cannot query `news_articles`, every public page (`HomePage`, `CategoryPage`, `ArticlePage`, `SearchPage`, `sitemap.xml`, `feed.xml`) receives empty data or 404/500 responses.
- **Recommended Correction:**
  1. Apply pending Alembic migrations (`0009_webz_io_migration` -> `0010_webz_field_expansion` -> `493f6e6a0c63`) to `.postgres_runtime` and verify schema parity with SQLAlchemy models.
  2. Fix `scripts/local_start.ps1` to temporarily set `$ErrorActionPreference = 'Continue'` around `python -m alembic upgrade head` and check `$LASTEXITCODE -ne 0` so `stderr` informational logs never abort migration execution.

---

### CRIT-02: Dead Navigation Links ("Culture" and "Opinion") Returning HTTP 404 & Missing Active Database Categories
- **Location / File / Component:**
  - `frontend/src/components/MainNavigation.tsx` (lines 7–18)
  - `frontend/src/components/SiteHeader.tsx` (lines 160–171)
  - `frontend/src/components/SiteFooter.tsx` (lines 179–200)
  - `frontend/src/app/category/[slug]/page.tsx` (lines 8–21, 49–52)
- **Actual Problem:**
  - `NAVIGATION_CATEGORIES` in `MainNavigation.tsx` and the mobile menu in `SiteHeader.tsx` link to `/category/culture` and `/category/opinion`.
  - Neither `"culture"` nor `"opinion"` exists in `CATEGORY_NAMES` in `frontend/src/app/category/[slug]/page.tsx` or in the `news_categories` table (`world`, `us`, `politics`, `business`, `technology`, `science`, `health`, `environment`, `sports`, `entertainment`).
  - Clicking "Culture" or "Opinion" in the header or footer returns a 404 page (`notFound()`).
  - Conversely, 4 active database categories with 167 published articles (`health`: 40, `environment`: 33, `sports`: 51, `entertainment`: 43) are completely unreachable from the header and footer navigation.
- **Severity:** **Critical**
- **Affects:** Frontend, UX, SEO
- **Why It Matters:** Broken links in the primary global navigation bar and footer immediately undermine reader trust and waste crawl budget, while hiding 40% of the platform's editorial categories.
- **Recommended Correction:**
  - Align `NAVIGATION_CATEGORIES` in `MainNavigation.tsx`, mobile links in `SiteHeader.tsx`, footer links in `SiteFooter.tsx`, and `CATEGORY_NAMES` in `category/[slug]/page.tsx` with the 10 real database categories (`us`, `world`, `politics`, `business`, `technology`, `science`, `health`, `environment`, `sports`, `entertainment`).
  - Support legacy alias slugs (`us-news` -> `us`, `culture` -> `entertainment`) via permanent `redirect()` to the canonical category slug so no bookmarks break and no duplicate canonicals exist.

---

### CRIT-03: Client-Side Search Page Hardcodes `/api/v1/articles` Without `lib/api.ts` or Next.js Proxy, Failing in Standalone Mode
- **Location / File / Component:**
  - `frontend/src/app/search/page.tsx` (lines 19–52)
  - `frontend/next.config.mjs` (lines 1–15)
  - `frontend/src/lib/api.ts` (lines 188–250)
- **Actual Problem:**
  - `search/page.tsx` performs `fetch('/api/v1/articles?q=...')` directly on line 29 instead of using `fetchArticles()` from `@/lib/api`.
  - When running locally on `http://localhost:3000` (Next.js standalone or dev server without Nginx), relative `/api/v1/...` requests go to port 3000 where no `/api/v1` route exists because `next.config.mjs` has no `rewrites()`.
  - Furthermore, `.catch()` on line 41 silently sets `results = []` without tracking an error state, so a failed network request is displayed to the user as `"No matching articles found"`.
  - Additionally, `searchTerm` input state is not synchronized when `queryParam` updates via the header search bar (`useEffect` does not update `searchTerm`).
- **Severity:** **Critical**
- **Affects:** Frontend, UX
- **Why It Matters:** Search is a core reader feature. Silently displaying "No matching articles found" when the request actually 404'd or failed is broken behavior.
- **Recommended Correction:**
  1. Add `rewrites()` in `frontend/next.config.mjs` proxying `/api/v1/:path*` to `${process.env.INTERNAL_API_URL || "http://127.0.0.1:8000/api/v1"}/:path*` so relative `/api/v1` calls work seamlessly in both standalone/dev and Nginx environments.
  2. Update `search/page.tsx` to use `fetchArticles` (or `getApiBaseUrl()`), distinguish between genuine `0 results` and an API/network error (`hasError` state), synchronize `searchTerm` with `queryParam`, and support pagination.

---

### CRIT-04: Fabricated News Headlines & Fake Publisher Attribution in Homepage Empty State
- **Location / File / Component:**
  - `frontend/src/app/page.tsx` (lines 189–220)
- **Actual Problem:**
  - In `HomePage`, when `wireArticles.length === 0`, the Live Wire Feed sidebar renders three hardcoded fake headlines:
    - `"Global Semiconductor Supply Chains Pivot Toward Automated Fabrication Hubs"` (`MetroScope Wire • Premier Publisher`)
    - `"Federal Reserve Signals Measured Monetary Adjustments Amid Treasury Yield Shifts"` (`MetroScope Wire • Premier Publisher`)
    - `"Transatlantic Energy Infrastructure Summit Concludes with Grid Modernization Compact"` (`MetroScope Wire • Premier Publisher`)
- **Severity:** **Critical**
- **Affects:** Frontend, Content
- **Why It Matters:** Directly violates Non-Negotiable Constraint #12 (*"Do not fabricate publisher names, article content, authors, publication dates, or source attribution"*) and Section 4.2 (*"Do not invent articles to fill empty sections"*). A news platform must never display invented news stories.
- **Recommended Correction:**
  - Remove all fabricated headlines from `frontend/src/app/page.tsx` and replace the fallback with an honest, clean empty state component if no wire stories are available.

---

### CRIT-05: Missing Tailwind Color Token Mappings (`foreground`, `muted`, `border`, `background`) & Unreadable Dark-Mode Logo
- **Location / File / Component:**
  - `frontend/tailwind.config.ts` (lines 12–47)
  - `frontend/src/app/globals.css` (lines 6–46)
  - `frontend/src/components/SiteHeader.tsx` (lines 88–95)
- **Actual Problem:**
  - `globals.css` defines `--background`, `--foreground`, `--border`, `--border-subtle`, `--muted`, and `--muted-foreground`, and every page/component uses `bg-background`, `text-foreground`, `text-muted`, `border-border`, `divide-border`, and `placeholder:text-muted`.
  - However, `tailwind.config.ts` never registered `background`, `foreground`, `border`, or `muted` under `theme.extend.colors`.
  - Inspecting the compiled `.next/static/css/*.css` confirmed that `.text-muted`, `.text-foreground`, `.border-border`, and `.bg-background` do not exist in the stylesheet. Consequently:
    - All `text-muted` secondary text and timestamps render in full body text color.
    - All `border-border` and `divide-border` dividers ignore `--border` and fall back to Tailwind preflight `#e5e7eb` (bright light gray even in dark mode).
  - Additionally, `public/logo.png` has dark navy lettering (`"Metro SCOPE"`). In `SiteHeader.tsx` (line 94), `dark:brightness-110` on dark navy (`#14213a`) leaves it dark navy against a `#0e1522` background, making the brand logo nearly invisible in dark mode (`docs/reports/screenshots/interaction_theme_toggled.png`).
- **Severity:** **Critical**
- **Affects:** Frontend, Brand & Visual Consistency, Accessibility
- **Why It Matters:** Broken design tokens degrade typography hierarchy on every page in light mode and break contrast/readability in dark mode.
- **Recommended Correction:**
  1. Register `background: "var(--background)"`, `foreground: "var(--foreground)"`, `border: { DEFAULT: "var(--border)", subtle: "var(--border-subtle)" }`, and `muted: { DEFAULT: "var(--muted)", foreground: "var(--muted-foreground)" }` in `frontend/tailwind.config.ts`.
  2. Style the logo container in `SiteHeader.tsx` (or apply appropriate dark-mode contrast treatment) so the official `logo.png` remains crisp and legible in both light and dark themes without altering `public/logo.png`.

---

### HIGH-01: Public API Schemas Expose Internal Provider, Deduplication, and Pipeline Metadata
- **Location / File / Component:**
  - `backend/app/schemas/article.py` (lines 21–57)
  - `frontend/src/lib/api.ts` (lines 19–50)
- **Actual Problem:**
  - `ArticleListItem` exposes internal fields `status`, `quality_score`, and `cluster_id`.
  - `ArticleDetail` exposes `uuid` (Webz.io internal identifier), `original_url`, `canonical_url_hash` (SHA-256 deduplication hash), `trust_indicators` (raw JSON string with `"provider": "webz.io"`, `"provider_domain_rank"`, `"provider_spam_score"`, `"provider_performance_score"`), `filter_reason` (internal relevance filter string), `discovered_at`, `created_at`, `sentiment`, and `webz_categories` (raw provider categories).
  - In `backend/app/schemas/source.py` and `category.py`, `SourceResponse` and `CategoryResponse` also expose internal DB timestamps `created_at` and `updated_at` and `is_active`.
- **Severity:** **High**
- **Affects:** Backend, Security, Content
- **Why It Matters:** Violates Phase C Requirements 1, 7, and 10 (*"Keep provider metadata separate from reader-facing editorial content"*, *"Ensure API responses expose only fields needed by public pages"*).
- **Recommended Correction:**
  - Restrict public response schemas (`ArticleListItem`, `ArticleDetail`, `SourceResponse`, `CategoryResponse`) to strictly reader-facing editorial fields (`id`, `title`, `slug`, `description`, `canonical_url`, `author`, `publisher_name`, `language`, `country`, `published_at`, `updated_at`, `is_trending`, `is_breaking`, `topics`, `source`, `category`).
  - Update `frontend/src/lib/api.ts` and backend API tests to match the sanitized public schema.

---

### HIGH-02: 136 Database Articles Contain Fabricated Placeholder Descriptions & External-Website Instructions
- **Location / File / Component:**
  - PostgreSQL `news_articles` (IDs 1–136)
  - `backend/scripts/clean_legacy_descriptions.py` (line 20)
  - `frontend/src/app/article/[slug]/page.tsx` (lines 197–206)
- **Actual Problem:**
  - 136 articles in `news_articles` have `description = "Comprehensive wire coverage and primary reporting. Access the original publication for full context."`
  - On the Article Detail Page, this fabricated boilerplate string is rendered inside the `"Article Summary"` box right above the `"Editorial Attribution & Direct Access Notice"` box, giving readers a fake summary and redundant instructions to visit an external website.
- **Severity:** **High**
- **Affects:** Content, Backend, Frontend
- **Why It Matters:** Directly violates Section 1 (*"placeholder content, and unnecessary external-source instructions. These must be identified and eliminated"*), Section 4.1 (*"Remove: Placeholder text. Misleading external website instructions"*), and Section 5 (*"Do not invent new editorial content to conceal data-quality problems"*).
- **Recommended Correction:**
  - Set `description = NULL` on the 136 articles where `description = 'Comprehensive wire coverage and primary reporting. Access the original publication for full context.'` so that articles without a real summary cleanly omit the summary box rather than displaying fake boilerplate text.
  - Ensure `frontend/src/app/article/[slug]/page.tsx` and list cards gracefully handle `description = null` with a clean editorial attribution layout.

---

### HIGH-03: Internal Server Hardware & Software Stack Specifications Exposed on Public "About Us" Page
- **Location / File / Component:**
  - `frontend/src/app/about/page.tsx` (lines 27–77)
- **Actual Problem:**
  - `/about` contains a `"Technology Infrastructure"` section reading: *"MetroScope is engineered as a resource-efficient modular monolith designed to operate smoothly within memory-constrained environments (2 vCPU, 2 GB RAM). Built with FastAPI, PostgreSQL, Next.js, and APScheduler..."* and `"Automated Normalization — Standardizing metadata, eliminating duplications, and classifying news items into structured editorial domains."*
- **Severity:** **High**
- **Affects:** Frontend, Content, Security
- **Why It Matters:** Exposes internal deployment architecture and server capacity (`2 vCPU, 2 GB RAM`, FastAPI, PostgreSQL, APScheduler) to the public and makes the site read like an engineering project report rather than an established digital news publication.
- **Recommended Correction:**
  - Rewrite `/about` with authentic editorial mission, journalistic curation standards, source attribution principles, and coverage scope—eliminating all references to server RAM/CPU, FastAPI, PostgreSQL, Next.js, APScheduler, and internal database normalization pipelines.

---

### HIGH-04: Unverified Third-Party Article Images Exposed in OpenGraph, Twitter Cards, and Schema.org JSON-LD
- **Location / File / Component:**
  - `frontend/src/app/article/[slug]/page.tsx` (lines 44, 75)
  - `frontend/src/lib/seo.ts` (lines 99, 115)
- **Actual Problem:**
  - In `article/[slug]/page.tsx`, `generateMetadata` sets `image: article.image_url || "/logo.png"` and `generateNewsArticleJsonLd` sets `imageUrl: article.image_url || undefined`.
  - As documented in `backend/app/integrations/webz/parser.py` (line 245), external `image_url` values from providers carry `"licensing_note": "Usage rights not verified. Display requires licensing confirmation."`
- **Severity:** **High**
- **Affects:** SEO, Copyright Compliance
- **Why It Matters:** Violates Non-Negotiable Constraint #10 (*"Never republish complete publisher articles or unauthorized third-party images"*) and Section 4.1 (*"Featured image only when usage rights are verified"*).
- **Recommended Correction:**
  - Use MetroScope's own verified brand card (`/logo.png`) in `generateMetadata` and `generateNewsArticleJsonLd` unless image licensing rights are explicitly verified, ensuring unauthorized third-party images are never syndicated in OpenGraph or Twitter cards.

---

### HIGH-05: Contact Page Simulates "Message Transmitted" Without Any Delivery Mechanism
- **Location / File / Component:**
  - `frontend/src/app/contact/page.tsx` (lines 11–16, 45, 54–61, 117–123)
- **Actual Problem:**
  - Submitting the Contact form calls `setSubmitted(true)` in client memory without sending an API request or opening an email client, and displays `"Message Transmitted — Thank you for contacting the MetroScope team. Our editorial staff will review your message promptly."`
  - Uses robotic terminology (`"Submit Transmission"`, `"Message Transmitted"`) and a `MapPin` icon next to `publishers@metroscope.news`.
- **Severity:** **High**
- **Affects:** Frontend, UX
- **Why It Matters:** Silently discarding reader corrections, DMCA/copyright requests, or editorial inquiries while claiming the message was transmitted is deceptive and poses legal/operational risk.
- **Recommended Correction:**
  - Update the Contact page so submitting the form opens a pre-populated `mailto:editorial@metroscope.news?subject=...&body=...` link (or clearly states it prepares an email to the appropriate editorial desk) alongside direct clickable `mailto:` links for Editorial Inquiries, Corrections, and Publisher/Copyright Relations, using professional editorial language (`"Send Inquiry"`).

---

### HIGH-06: Non-Article Junk Pages, Foreign-Language Posts, Truncated Descriptions in DB & Missing Quality Gate in `WebzIngestionService`
- **Location / File / Component:**
  - `backend/app/services/webz_ingestion_service.py` (lines 235–295)
  - `backend/app/integrations/webz/parser.py` (lines 58–92, 124–127)
  - PostgreSQL `news_articles`
- **Actual Problem:**
  1. **Missing Quality & Relevance Gate in `WebzIngestionService`:** `run_category_collection` computes `quality = self.quality_service.score_article(...)` (with hardcoded `category_confidence=10` instead of `art.classification_confidence`), but never filters out low-scoring or spam/non-news records before inserting them with `status="published"`.
  2. **Synthetic Redundant Summary Fallback in `webz/parser.py`:** When `post.summary` is empty, `extract_short_summary()` fabricates `"Reporting by {publisher}: {headline}."`, which simply repeats the article headline inside the summary box.
  3. **Junk / Non-Editorial Records Currently Published in `news_articles`:**
     - Non-article website pages: ID 71 (`"IOPscience terms & conditions"`), ID 74 (`"Subject collections"`), ID 78 (`"Open access - IOPscience"`), ID 88 (`"About IOPscience"`), ID 133 (`"Accessibility statement"`), ID 136 (`"multi X 2500 | AOX systems"`).
     - Malformed/truncated fragments: ID 9 (`"🏀 Kaufman"`), ID 8 (`"Foo Fighters Launch Australian Tour With 26"`), ID 23 (`"East Coast soaker threatens millions in Northeast with flash flooding , while Mid"`), ID 33 (`"A matter of timing"`), ID 34 (`"Stock Market Faces a Worst"`), ID 108 (`"Clippers snap 7"`), ID 112 (`"Sharks try to halt 5"`).
     - Non-English articles marked `language='en'` and `country='US'`: ID 1 (Spanish), ID 4 (Portuguese), ID 17 (Spanish), ID 29 (French), ID 30 (French e-commerce product listing `"Capteur De Température étanche Thermomètre Moto..."`).
     - 60 legacy headlines with GDELT punctuation spacing artifacts (`" , "`, `" : "`, `" . "`, `"4 %"`).
     - 51 RSS descriptions containing raw `[…]` or `\u200b` zero-width space characters or ending mid-clause without punctuation.
- **Severity:** **High**
- **Affects:** Backend, Content
- **Why It Matters:** Violates Phase C Requirement 2 (*"Never use raw provider metadata as a public article description"*) and Requirement 8 (*"Ensure invalid or low-quality records do not appear as polished published articles"*).
- **Recommended Correction:**
  1. In `WebzIngestionService`, pass `art.classification_confidence` into `score_article()`, invoke `RelevanceService` / minimum quality threshold, and set `status="filtered"` (incrementing `stats["filtered"]`) for non-editorial, spam, or low-quality items.
  2. In `webz/parser.py`, return `None` from `extract_short_summary` when no real summary exists (rather than synthesizing `"Reporting by ...: <headline>."`), reject non-English posts (`language != "english"`), and reject utility page titles (`terms & conditions`, `accessibility statement`, `privacy policy`, `about us`).
  3. In `normalizer_service.py`, normalize tokenized punctuation spacing (`" , "` -> `", "`, `" : "` -> `": "`), strip zero-width spaces (`\u200b`), and clean `[…]` to `...`.
  4. Transition the identified junk/non-English/fragment records in `news_articles` to `status='filtered'` (preserving the database rows non-destructively per Constraint #14 while removing them from public display) and clean punctuation spacing on published headlines.

---

### HIGH-07: Raw Domain Strings Used as Publisher Display Names on 105/114 Sources & Forced `country='US'` Default
- **Location / File / Component:**
  - PostgreSQL `news_sources` (105 of 114 rows)
  - `backend/app/repositories/source_repository.py` (lines 16–50)
  - `backend/app/integrations/webz/parser.py` (lines 38–55, 150–166)
  - `backend/alembic/versions/20261111_1302_493f6e6a0c63_allow_unknown_article_and_source_.py`
- **Actual Problem:**
  1. 105 of 114 sources in `news_sources` have raw domain names as their `name` (e.g., `Deperu.com`, `550thezone.iheart.com`, `Nyc-shows.brooklynvegan.com`, `Theintelligencer.net`, `Klcc.org`).
  2. In `webz/parser.py`:
     - `_resolve_publisher_name()` falls back to `thread.site_full` / `thread.site` (raw domain) when `thread.site_title` is absent.
     - `normalize_webz_post()` uses `thread.site` before `extract_domain(canonical_url)`, which can mismatch subdomains or canonical URLs.
  3. Migration `493f6e6a0c63` changed `country` to `nullable=True` on `news_articles` and `news_sources` without dropping the PostgreSQL `server_default='US'` created in migration `0002`, and `news_sources` has non-US outlets (`pt.euronews.com`, `crhoy.com`, `courrierinternational.com`, `deperu.com`, `bbc.com`) marked `country='US'`.
- **Severity:** **High**
- **Affects:** Backend, Content, Frontend
- **Why It Matters:** Violates Phase C Requirements 4, 5, and 6 (*"Preserve publisher attribution"*, *"Avoid incorrect publisher-domain extraction"*, *"Unknown country must not silently become US"*).
- **Recommended Correction:**
  1. Add a clean publisher name formatter in `source_repository.py` / `normalizer_service.py` (mapping known domains and formatting domain names cleanly without raw `.com`/`.org`/subdomain clutter when `site_title` is unavailable, while preserving the exact `domain` field in `news_sources.domain`).
  2. In `webz/parser.py`, extract `domain` authoritatively from `extract_domain(canonical_url)` (falling back to `extract_domain(thread.site_full)`), and only set `publisher_name` from `thread.site_title` (cleaned) or the formatted source name.
  3. Drop `server_default` on `news_articles.country` and `news_sources.country`, and set `country = NULL` on sources/articles where country was not genuinely verified as US.

---

### MED-01: Internal / Scraper Terminology & Verbose Disclaimer Copy Across Public Pages
- **Location / File / Component:**
  - `frontend/src/app/article/[slug]/page.tsx` (lines 35, 41, 138, 164, 181, 208–228)
  - `frontend/src/app/category/[slug]/page.tsx` (lines 41, 91, 99, 120, 133, 150, 157–172)
  - `frontend/src/app/search/page.tsx` (lines 76, 97, 100, 106, 114, 126, 143)
  - `frontend/src/app/not-found.tsx` (lines 18, 22)
- **Actual Problem:**
  - **Article Detail Page (`article/[slug]/page.tsx`):**
    - Appends `"— News Discovery"` to `<title>`.
    - Displays publisher name in monospace code font (`font-mono`).
    - Shows a badge `"Publisher Attributed"` in the header and a heavy technical box `"Editorial Attribution & Direct Access Notice — MetroScope respects copyright law... full article bodies are not stored or duplicated..."`.
  - **Category Page (`category/[slug]/page.tsx`):**
    - Heading `"Discovered Reports (N)"`.
    - Fallback timestamp `"Real-time Normalized"`.
    - Link to internal article page says `"Read Discovery Dispatch"` with an `ExternalLink` icon.
    - Empty state is a fake `<article>` titled `"{categoryName} Sector Intelligence"` with `"Real-time Ingestion Active"` and `"Automated index record tracking verified publication signals... Full normalization pipeline ensures structural deduplication."`
  - **Search Page (`search/page.tsx`):**
    - Heading `"Search News Discovery Archive"`, status `"Showing X of Y verified discovery records"`, `"Querying news discovery archive..."`, fallback date `"Indexed"`, link `"View Record"` with `ExternalLink` icon.
- **Severity:** **Medium**
- **Affects:** Frontend, Content, UX
- **Why It Matters:** Directly addressed by Section 1 & Section 4.1–4.4: the website must read like a professional digital news publication, not an automated scraper or database index viewer.
- **Recommended Correction:**
  - Replace all internal/scraper phrasing across `article/[slug]/page.tsx`, `category/[slug]/page.tsx`, `search/page.tsx`, and `not-found.tsx` with clean, standard editorial terminology.
  - On the Article Detail Page, present a clear, refined editorial attribution card showing the original publisher name, domain, publication date/time, a concise distinction between MetroScope's summary and original reporting, and a prominent `"Read Full Article at {sourceName}"` outbound link.
  - Replace `ExternalLink` icons on internal `/article/[slug]` links with `ArrowRight` / `ArrowUpRight`.

---

### MED-02: Duplicate Category Routes (`/category/us` vs `/category/us-news`, `/category/business` vs `/category/markets`) Creating Duplicate Canonical URLs
- **Location / File / Component:**
  - `frontend/src/app/category/[slug]/page.tsx` (lines 8–21, 39–43, 54–55)
  - `frontend/src/components/MainNavigation.tsx` (lines 9, 13)
- **Actual Problem:**
  - `/category/us-news` renders the exact same articles as `/category/us`, but sets its canonical URL to `/category/us-news`.
  - `/category/markets` renders the exact same articles as `/category/business`, but sets its canonical URL to `/category/markets` and titles the page `"Financial Markets"`.
- **Severity:** **Medium**
- **Affects:** SEO, Frontend
- **Why It Matters:** Violates Phase E (*"Do not create duplicate canonical URLs"*) and Section 4.3 (*"Category filters do not display misleading results"*).
- **Recommended Correction:**
  - Standardize navigation on the 10 canonical category slugs (`/category/us`, `/category/world`, `/category/politics`, `/category/business`, `/category/technology`, `/category/science`, `/category/health`, `/category/environment`, `/category/sports`, `/category/entertainment`).
  - Redirect legacy alias slugs (`us-news` -> `/category/us`, `markets` -> `/category/business`, `culture` -> `/category/entertainment`) via Next.js `redirect()`.

---

### MED-03: Missing Pagination on Category Pages and Search Page
- **Location / File / Component:**
  - `frontend/src/app/category/[slug]/page.tsx` (line 57)
  - `frontend/src/app/search/page.tsx` (line 29)
- **Actual Problem:**
  - `CategoryPage` ignores `searchParams.page` and always fetches `{ page: 1, pageSize: 20 }`, rendering no pagination controls even when `data.total_pages > 1` (e.g. `us` has 5 pages of articles).
  - `SearchPage` also hardcodes `page=1` with no pagination UI.
- **Severity:** **Medium**
- **Affects:** Frontend, UX, SEO
- **Why It Matters:** Section 4.3 requires *"Pagination or existing navigation works."* Without pagination, over 70% of published articles in major categories cannot be browsed.
- **Recommended Correction:**
  - Read `searchParams.page` in `CategoryPage` and `SearchPage`, pass `page` to the API call, and render accessible `Previous` / `Page X of Y` / `Next` pagination controls when `total_pages > 1`.

---

### MED-04: Schema.org `NewsArticle` Structured Data Misattributes Third-Party Articles
- **Location / File / Component:**
  - `frontend/src/lib/seo.ts` (lines 91–139)
  - `frontend/src/app/article/[slug]/page.tsx` (lines 58, 67–76)
- **Actual Problem:**
  - `generateNewsArticleJsonLd` sets `publisher` to MetroScope and `author` to `sourceName || "Syndicated Discovery"`, ignoring `article.author` when present and omitting `isBasedOn` (the original canonical URL at the source publisher).
- **Severity:** **Medium**
- **Affects:** SEO, Content
- **Why It Matters:** Phase E requires: *"Do not fabricate article authors. Do not invent publication dates. Do not add structured data that misrepresents third-party articles. Ensure article metadata accurately reflects MetroScope's actual role as a discovery and summary platform."*
- **Recommended Correction:**
  - Update `generateNewsArticleJsonLd` in `frontend/src/lib/seo.ts` to include `isBasedOn: canonicalUrl` (pointing to the original publisher's URL), use the real `author` (or source organization when individual author is not listed, never `"Syndicated Discovery"`), and accurately represent the summary page.

---

### MED-05: Two Failing Backend Regression Tests & Scheduler Job Naming Mismatch
- **Location / File / Component:**
  - `backend/tests/test_phase10_ux_regression.py` (lines 18–31)
  - `backend/tests/test_phase12_content_expansion.py` (lines 38–44)
  - `backend/app/integrations/webz/client.py` (lines 38–46)
  - `backend/app/workers/jobs.py` (lines 13–49)
  - `backend/app/workers/scheduler.py` (lines 31–60)
- **Actual Problem:**
  1. `test_article_page_markup_mobile_overflow_prevention` fails because it asserts `"break-all"` and `"overflow-hidden"` in `frontend/src/app/article/[slug]/page.tsx` (which were previously on the removed SHA-256 hash box).
  2. `test_scheduled_categories_in_webz_queries` fails because it asserts `"sports" in CATEGORY_QUERIES`, while `CATEGORY_QUERIES` in `webz/client.py` now defines `default`, `confirmed`, `business`, `science`, and `technology`. Meanwhile, `jobs.py` and `scheduler.py` still name the morning job `collect_webz_sports_morning_job` (`category="sports"`), which silently falls back to `CONFIRMED_QUERY` (`business/finance OR science/technology`) in `WebzClient.build_query()`.
- **Severity:** **Medium**
- **Affects:** Backend, QA
- **Why It Matters:** All tests must pass honestly and reflect actual application behavior.
- **Recommended Correction:**
  - Align `CATEGORY_QUERIES`, `jobs.py`, `scheduler.py`, and `test_phase12_content_expansion.py` so the scheduled Webz.io jobs and category query mappings are consistent, and ensure `article/[slug]/page.tsx` includes proper mobile overflow protection (`break-words` / `overflow-hidden`) verified by `test_phase10_ux_regression.py`.

---

### LOW-01: Verify Subscription & Unsubscribe Pages Use Hardcoded Light-Mode Colors & Broken Dark-Mode Button Contrast
- **Location / File / Component:**
  - `frontend/src/app/verify-subscription/page.tsx` (lines 69–106)
  - `frontend/src/app/unsubscribe/page.tsx` (lines 69–116)
- **Actual Problem:**
  - Both pages use hardcoded `bg-white border-gray-100 text-gray-900` cards and `bg-primary text-white` buttons. In dark mode, `--primary` is `#f8f9fa` (near-white), resulting in white text on a white button.
- **Severity:** **Low**
- **Affects:** Frontend, Brand Consistency, Accessibility
- **Why It Matters:** Breaks dark-mode readability and visual consistency on newsletter confirmation and unsubscription flows.
- **Recommended Correction:**
  - Replace hardcoded gray/white classes with Stitch design tokens (`bg-surface-lowest border-border text-foreground`, `text-muted`, and `bg-secondary text-white` / `bg-metro-navy text-white`).

---

### LOW-02: Untracked Review Bundle Files in Workspace Root
- **Location / File / Component:**
  - `metroscope_review_bundle.txt`, `metroscope_review_supplement.txt`, `.gitignore`
- **Actual Problem:**
  - Two large text dump files (`metroscope_review_bundle.txt` and `metroscope_review_supplement.txt`) sit untracked in the repository root.
- **Severity:** **Low**
- **Affects:** Repository Hygiene
- **Why It Matters:** Prevents accidental commit of review dump artifacts.
- **Recommended Correction:**
  - Add `metroscope_review_*.txt` to `.gitignore` (preserving files safely per Constraint #14).

---

### LOW-03: Static "Breaking Wire" Ticker Badge on Every Page & "Discovered Story" Phrasing in RSS Feed
- **Location / File / Component:**
  - `frontend/src/components/SiteHeader.tsx` (lines 121–132)
  - `frontend/src/app/feed.xml/route.ts` (lines 34–38)
- **Actual Problem:**
  - `SiteHeader.tsx` displays a pulsing `"Breaking Wire"` badge with a static tagline on every page regardless of whether breaking news exists.
  - `feed.xml/route.ts` uses `"Syndicated Wire"` and `"Discovered story from ${sourceName}..."`.
- **Severity:** **Low**
- **Affects:** Frontend, Content
- **Why It Matters:** Overusing a pulsing "Breaking" indicator when no breaking headline is shown reduces editorial credibility.
- **Recommended Correction:**
  - Change the static masthead sub-bar in `SiteHeader.tsx` to a refined editorial edition bar (e.g., `"Editorial Desks"` / `"National & International Coverage"` without a false pulsing breaking alarm), and refine the fallback description in `feed.xml/route.ts`.

---

## 4. Proposed Execution Plan (Phases B – H)

Pending your review of this Phase A audit, we will execute the corrections in small, verifiable groups:

1. **Group 1 — Database Schema Synchronization & Content/Source Data Remediation (Phase C Foundation):**
   - Apply pending Alembic migrations (`0009`, `0010`, `493f6e6a0c63`) to `.postgres_runtime` and drop the legacy `server_default='US'` on `country` columns via a clean migration.
   - Fix `scripts/local_start.ps1` stderr handling so `alembic upgrade head` never aborts on `INFO` logs.
   - Clean the 136 fabricated placeholder descriptions (`SET description = NULL`), filter out the 11 non-article utility/foreign/fragment records (`SET status = 'filtered'`), repair GDELT punctuation spacing on headlines, and format display names on `news_sources` so raw domains like `550thezone.iheart.com` are replaced with clean publisher names.
2. **Group 2 — Backend API Schemas, Normalization & Webz.io Pipeline Hardening (Phase C & F):**
   - Sanitize `ArticleListItem`, `ArticleDetail`, `SourceResponse`, and `CategoryResponse` so no internal provider/pipeline fields (`uuid`, `canonical_url_hash`, `trust_indicators`, `webz_categories`, `filter_reason`, `quality_score`, `cluster_id`) leak publicly.
   - Harden `WebzIngestionService` and `webz/parser.py` (quality/relevance gate, no synthetic headline-repeating summaries, authoritative domain extraction, consistent scheduler/query alignment).
3. **Group 3 — Design System Tokens, Header, Navigation & Footer (Phase B & D):**
   - Register `background`, `foreground`, `border`, and `muted` in `frontend/tailwind.config.ts` and ensure dark-mode logo legibility in `SiteHeader.tsx`.
   - Align `MainNavigation.tsx`, `SiteHeader.tsx`, and `SiteFooter.tsx` with the 10 canonical categories (`us`, `world`, `politics`, `business`, `technology`, `science`, `health`, `environment`, `sports`, `entertainment`).
4. **Group 4 — Article Detail Page, Homepage, Category Pages, Search & Informational Pages (Phase B & E):**
   - Transform `article/[slug]/page.tsx` with clean editorial attribution, proper source links, and zero internal/scraper jargon.
   - Remove the 3 fabricated headlines from `page.tsx` and refine homepage empty/card states.
   - Add pagination and clean empty states to `category/[slug]/page.tsx` and redirect legacy category aliases (`us-news`, `markets`, `culture`, `opinion`).
   - Fix `search/page.tsx` API integration, add `/api/v1` rewrite in `next.config.mjs`, add error state and pagination.
   - Rewrite `/about` (removing server/stack specs), fix `/contact` (`mailto:` inquiry dispatch), and fix dark-mode styling on `/verify-subscription` and `/unsubscribe`.
   - Update `lib/seo.ts` (`generateNewsArticleJsonLd` with `isBasedOn`, verified logo image fallback for OpenGraph/Twitter).
5. **Group 5 — Full QA, Automated Tests, Live Browser Verification & Release Checklist (Phase G & H):**
   - Run full backend `pytest` suite, frontend `tsc --noEmit`, `next lint`, and `next build`.
   - Start the local stack and inspect Desktop, Tablet, and Mobile layouts across all pages in the browser.
   - Produce `docs/PRODUCTION_RELEASE_CHECKLIST.md`.


---

## 5. Remediation Execution and Verification Report (Groups 1–5)

**Execution Status:** Fully Executed & Verified (November 12, 2026)  
**Overall Release Verdict:** **READY WITH KNOWN LIMITATIONS**

### 5.1 Finding Resolution Matrix

| Finding ID | Severity | Description | Remediation Group | Resolution Status | Verification Method |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **CRIT-01** | Critical | Unapplied DB migrations & PowerShell stderr abort | Group 1 | **RESOLVED** | Migrations up to `0011` applied; `local_start.ps1` fixed; `articles` API returns 200 OK |
| **CRIT-02** | Critical | Dead navigation links (`culture`, `opinion`) | Group 3 & 4 | **RESOLVED** | Header/footer updated with all 10 canonical categories; redirects added |
| **CRIT-03** | Critical | Search fails in standalone mode | Group 4 | **RESOLVED** | Replaced direct fetch with `fetchArticles`; Next.js API rewrite configured |
| **CRIT-04** | Critical | Fabricated headlines in homepage empty state | Group 4 | **RESOLVED** | Fabricated headlines removed; clean editorial empty state rendered |
| **CRIT-05** | Critical | Missing Tailwind theme tokens & dark-mode logo | Group 3 | **RESOLVED** | Tokens mapped in `tailwind.config.ts`; dark mode pill added for logo |
| **HIGH-01** | High | Public API schemas expose internal fields | Group 2 | **RESOLVED** | Schemas sanitized (`uuid`, `quality_score`, `cluster_id` stripped) |
| **HIGH-02** | High | 136 fabricated placeholder summaries in DB | Group 1 | **RESOLVED** | Cleared 136 placeholder descriptions to `NULL` via non-destructive update |
| **HIGH-03** | High | About page exposes server hardware specs | Group 4 | **RESOLVED** | Server specs removed; replaced with journalistic mission statement |
| **HIGH-04** | High | Unverified third-party images in OpenGraph | Group 4 | **RESOLVED** | Verified brand logo fallback configured in `lib/seo.ts` |
| **HIGH-05** | High | Contact page fakes transmission / dead links | Group 4 & 5 | **RESOLVED** | Replaced unverified emails with truthful platform & publisher guidance |
| **HIGH-06** | High | Non-article utility pages & missing quality gate | Group 1 & 2 | **RESOLVED** | Filtered 6 non-articles in DB; quality gate integrated in ingestion |
| **HIGH-07** | High | Raw domain strings for publishers & forced US | Group 1 | **RESOLVED** | Normalized 101 publisher names; migration `0011` dropped US default |
| **MED-01** | Medium | Scraper/pipeline jargon across UI | Group 4 | **RESOLVED** | Replaced technical jargon with clean journalistic terminology |
| **MED-02** | Medium | Duplicate category routes with conflicting SEO | Group 4 | **RESOLVED** | Permanent redirects added for alias slugs (`us-news`, `markets`, etc.) |
| **MED-03** | Medium | Missing pagination on Category and Search | Group 4 | **RESOLVED** | Pagination controls implemented for Category and Search views |
| **MED-04** | Medium | Schema.org JSON-LD missing source attribution | Group 4 | **RESOLVED** | `isBasedOn` linking to original publishers added to `NewsArticle` schema |
| **MED-05** | Medium | Failing pytest regression tests | Group 2 & 5 | **RESOLVED** | Scheduler name and tests aligned; 157/157 tests passing |
| **LOW-01** | Low | Newsletter verify/unsubscribe styling | Group 4 | **RESOLVED** | Styled with design tokens and dark mode support |
| **LOW-02** | Low | Untracked review dump files | Group 1 | **RESOLVED** | Added `metroscope_review_*.txt` to `.gitignore` |
| **LOW-03** | Low | Static "Breaking Wire" pulse badge | Group 3 | **RESOLVED** | Replaced with "Latest Coverage" editorial edition sub-bar |

### 5.2 Summary of Verification Evidence

1. **Automated Backend Regression Tests:**
   - Command: `python -m pytest -v backend/tests`
   - Outcome: **157 passed, 0 failed, 2 warnings** in 5.88s (100% pass rate).
2. **Frontend Production Build:**
   - Command: `npm --prefix frontend run build`
   - Outcome: **Exit code 0**; 14 static and dynamic routes compiled cleanly.
3. **Local Runtime & Browser Verification:**
   - Stack: PostgreSQL (`.postgres_runtime`:5433), FastAPI (127.0.0.1:8000), Next.js (localhost:3000).
   - Outcome: 10/10 target views returned HTTP 200 OK. Zero prohibited debug strings, internal column names, scraper jargon, or unconfirmed email addresses detected.
4. **Final Deliverable:**
   - Detailed production checklist, operational limits, and deployment sign-off recorded in `docs/PRODUCTION_RELEASE_CHECKLIST.md`.

---

## 5.3 Local Full Production Simulation & Comprehensive Acceptance Audit (November 13, 2026)

**Auditor:** Senior DevOps Engineer, QA Automation Engineer & Release Engineer  
**Simulation Configuration:**
- **PostgreSQL Persistent Cluster:** `127.0.0.1:5433` (`.postgres_runtime`, 495 published articles, 114 sources, 10 categories, Migration HEAD `0011_drop_country_server_default`)
- **FastAPI API Server:** `http://127.0.0.1:8000` (`ENVIRONMENT=production`, `DEBUG=false`, Security Headers `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`)
- **Next.js Standalone Production Server:** `http://localhost:3000` (`node .next/standalone/server.js`, pre-rendered static chunks, `/api/v1/*` proxy rewrites)
- **APScheduler Background News Worker:** `python -m app.workers.main` (Morning Sports 08:00 Asia/Dhaka, Evening Business 20:00 Asia/Dhaka, Social Publisher 30m Dry-Run, Newsletter Briefing 06:00 UTC Dry-Run)
- **Local Email Capture:** `logs/captured_emails.log` (`LOCAL_CAPTURE_NOT_DELIVERED`)
- **Automated Browser Automation Engine:** Headless Google Chrome via Puppeteer-Core (`scripts/browser_functional_test.js`)

### Acceptance Testing Results Summary

| Testing Domain | Command / Method | Output / Evidence | Status |
| :--- | :--- | :--- | :---: |
| **Backend Test Suite** | `python -m pytest backend/tests -v` | 157 passed, 0 failed, 2 warnings in 6.04s | **PASS** |
| **Frontend Typecheck** | `npm --prefix frontend run typecheck` | `tsc --noEmit` exited with code 0 (0 errors) | **PASS** |
| **Frontend Lint** | `npm --prefix frontend run lint` | `next lint` exited with code 0 (0 warnings, 0 errors) | **PASS** |
| **Frontend Standalone Build** | `npm --prefix frontend run build` | Next.js standalone build complete, all 14 routes compiled | **PASS** |
| **DB Migrations & Storage** | `alembic current` & `psql` | Active cluster at `0011_drop_country_server_default`, 495 articles intact | **PASS** |
| **Health & Probe Endpoints** | `scripts/verify_all_endpoints.py` | `/health`, `/health/live`, `/health/ready`, `/health/metrics` all return HTTP 200 | **PASS** |
| **10 Category Routes** | `scripts/verify_all_endpoints.py` | All 10 categories (`us`, `world`, `politics`, `business`, `technology`, `science`, `health`, `environment`, `sports`, `entertainment`) return HTTP 200 | **PASS** |
| **Search & Pagination** | `scripts/verify_all_endpoints.py` & Chrome | Client-side search & pagination functional, zero broken queries | **PASS** |
| **Content & Publisher Attribution** | API & Chrome DOM inspection | Clean broadsheet layout, verified publisher name & canonical URL attribution | **PASS** |
| **RSS & Sitemap Feeds** | `scripts/verify_all_endpoints.py` | `/rss.xml`, `/feed.xml`, `/sitemap.xml`, `/robots.txt` return HTTP 200 valid XML/text | **PASS** |
| **Browser Responsive Testing** | `scripts/browser_functional_test.js` | 5 viewports (1440px, 1366px, 768px, 390px, 360px), 0 overflows, 0 console errors | **PASS** |
| **Newsletter Flow (Local Capture)**| Form submit & `logs/captured_emails.log` | Token generated, message captured without external delivery, verify & unsub pages return 200 | **PASS** |
| **Social Publishing Dry-Run** | `logs/worker.log` & unit tests | Meta Graph & X API v2 formatting & limits verified in safe dry-run mode | **PASS** |
| **Webz.io API Pipeline Logic** | `test_webz_integration.py` | Budget protection, deduplication, schema validation, persistence verified in test suite | **PASS** |
| **Live External Webz.io HTTP** | `backend/scripts/smoke_test_webz.py` | Blocked until user inputs production `WEBZ_IO_API_KEY` in `.env` | **PARTIAL** |
| **Live External SMTP Delivery** | SMTP Relay | Blocked until user inputs production SMTP credentials in `.env` | **PARTIAL** |
| **Live Public Social Posting** | Facebook & X Live APIs | Blocked until user approves public accounts and sets API tokens in `.env` | **PARTIAL** |
| **Live AWS Cloud Infrastructure** | AWS Deployment | Intentionally withheld until manual user testing sign-off | **PARTIAL** |

---

## 5.4 Full Article Body Rendering, Content Rights Authorization Engine & Article Detail UI Verification (November 13, 2026)

**Auditor:** Senior DevOps Engineer, QA Automation Engineer & Release Engineer  
**Scope:** Webz.io content pipeline (`post.text` vs `post.summary` vs `post.thread.text`), Alembic migration `0012_article_full_text_rights`, `ContentRightsService` licensing engine, article detail UI redesign (redundant attribution box removal), and 5-scenario content matrix verification.

### Scope & Architectural Implementation
1. **Webz.io Content Pipeline:**
   - Evaluated root-level Webz.io `text` field and extracted it strictly as `full_text` in `NormalizedWebzArticle`.
   - Distinct from `post.summary` (stored as `description`) and `post.thread.text` (thread root).
   - Preserves original language and paragraph boundaries without machine translation, truncation, or synthetic rewriting.
2. **Database Migration `0012_article_full_text_rights`:**
   - Added nullable `full_text` (`sa.Text()`) and non-nullable `content_display_authorized` (`sa.Boolean()`, default `false`).
   - Revision ID constrained to <= 32 characters (`0012_article_full_text_rights`, 27 chars) to comply with PostgreSQL `alembic_version.version_num VARCHAR(32)`.
   - Safely migrated database to HEAD without dropping or resetting tables; all 495+ existing articles preserved intact.
3. **Content Licensing & Publication Rights Engine (`ContentRightsService`):**
   - Automatically whitelists statutory public domain publishers (e.g. U.S. Federal government works under 17 U.S.C. § 105 like `nasa.gov`, `cdc.gov`, `noaa.gov`, `state.gov`).
   - Disregards crawler directives (`ai_allow: true`) and external Creative Commons (CC BY) links as republication permissions.
   - Enforces default summary-only presentation for commercial news publishers unless explicit syndication license is established.
4. **Article Detail Page Redesign (`frontend/src/app/article/[slug]/page.tsx`):**
   - **Removed Redundant Attribution Box:** Completely excised the separate `"Original Reporting by [Publisher]"` container, duplicate source URL display, and redundant publisher description.
   - **Maintained Headline Attribution:** Preserved the `"Originally published by [Publisher]"` header row with direct external link.
   - **Authorized Full Text Body:** Displays multi-paragraph article body with typography styling (`prose`, `leading-relaxed`, `break-words`, `break-all`) when `content_display_authorized && full_text`.
   - **Content Fallback:** When full text is missing or unauthorized, displays permitted summary with publisher link without fabricating text or displaying misleading full-article badges.

### Acceptance & Verification Results Matrix

| Verification Requirement | Test / Tool | Actual Output / Result | Status |
| :--- | :--- | :--- | :---: |
| **English Article with Full Text** | `scripts/verify_full_text_matrix.py` | Full multi-paragraph body rendered on `http://localhost:3000/article/test-auth-english-fulltext` | **PASS** |
| **Non-English Unicode Article** | `scripts/verify_full_text_matrix.py` | Intact Bengali Unicode script rendered without corruption on `http://localhost:3000/article/test-auth-unicode-bangla` | **PASS** |
| **Commercial Article Masking** | `scripts/verify_full_text_matrix.py` | Proprietary `full_text` masked to `None` on `/api/v1/articles/test-unauth-commercial-masked`; summary fallback rendered | **PASS** |
| **Summary-Only Wire Article** | `scripts/verify_full_text_matrix.py` | `full_text = None`, permitted summary displayed with publisher link | **PASS** |
| **Headline-Only Article** | `scripts/verify_full_text_matrix.py` | Both `full_text` & `description` are `None`; rendered clean publisher link without fabricated paragraphs | **PASS** |
| **Attribution Box Removal** | Live HTML string inspection | `Original Reporting by` and `Source: ` absent from all article pages | **PASS** |
| **Backend Full Test Suite** | `python -m pytest backend/tests -v` | **165 passed, 0 failed, 2 warnings** in 5.58s | **PASS** |
| **Full Text Unit Test Suite** | `pytest backend/tests/test_article_full_text.py` | **12 passed, 0 failed** in 0.18s | **PASS** |
| **Frontend Typecheck** | `npm --prefix frontend run typecheck` | `tsc --noEmit` exited with 0 errors | **PASS** |
| **Frontend Lint** | `npm --prefix frontend run lint` | `next lint` exited with 0 warnings, 0 errors | **PASS** |
| **Frontend Production Build** | `npm --prefix frontend run build` | Next.js standalone production build generated cleanly | **PASS** |
| **Database Preservation** | `SELECT COUNT(*) FROM news_articles` | 500 articles preserved intact in `.postgres_runtime` | **PASS** |

---

## 5.5 Clean Article Dataset, Webz.io Validation & Single-Page Editorial Reading Platform Rebuild (November 14, 2026)

**Auditor:** Senior Full-Stack Engineer, Data Engineer, Editorial UI/UX Engineer & QA Lead  
**Scope:** Controlled article dataset cleanup (Phase 1), Webz.io schema mapping and validation (Phase 2 & 5), strict Content & Image Rights Policy (Phase 3), single-page broadsheet reading experience (Phase 4 & 6), global publication flow (Phase 7), and comprehensive 12-scenario test matrix verification (Phase 8).

### 1. Database Backup & Controlled Data Cleanup (Phase 1)
- **Active Runtime Identified:**
  - Cluster: `.postgres_runtime` at `127.0.0.1:5433`, DB `metroscope`.
  - Alembic Head Revision: `0012_article_full_text_rights`.
- **Pre-Cleanup Backup Verification:**
  - `backups/metroscope_backup_pre_cleanup_20261114_052203Z.dump` (165,324 bytes, 117 TOC items verified via `pg_restore.exe -l`).
  - `backups/metroscope_backup_pre_cleanup_20261114_052203Z.sql` (442,979 bytes).
- **Controlled Data Reset:**
  - Before cleanup: `news_articles` = 506 (500 published, 6 filtered; IDs 1–507), `social_posts` = 8, `news_sources` = 114, `news_categories` = 10, `email_subscribers` = 1, `discovery_ingestion_runs` = 23.
  - Purged 8 dependent `social_posts` and 506 `news_articles` (including synthetic test IDs 503–507 and legacy production articles).
  - Reset sequences `news_articles_id_seq` and `social_posts_id_seq` to 1.
  - Preserved 100% of master data: 114 sources, 10 categories, 1 subscriber, 23 ingestion runs, and full schema/migration history.
  - After cleanup verified: `news_articles` = 0.
  - Seeded 5 clean test matrix records (IDs 1–5) for rigorous acceptance verification.

### 2. Webz.io Response Schema Mapping & Editorial Validation (Phase 2 & 5)
- **Direct Schema Mapping Without Fabrication:**
  - `thread.title` -> Headline.
  - `thread.main_image` -> Hero image candidate.
  - Root `text` -> Authentic full body text (persisted as `full_text`). Root `text` is never silently replaced by summary or thread text.
  - Root `summary` -> Short summary (persisted as `description`).
  - `language`, `author`, `url`, `published`, `site`, `site_full` mapped directly.
  - `internal_images` / `external_images` mapped with captions, credits, and dimensions.
- **Pre-Publication Editorial Validation (`ArticleEditorialValidationService`):**
  - Structural schema integrity and presence of title and source.
  - Valid canonical URL; rejects private RFC 1918 / loopback IPs.
  - Valid publication date; rejects future timestamps or articles > 30 days old.
  - Rejects navigation menus, cookie walls, paywalls, and boilerplate text.
  - Rejects tracking pixels (`pixel.gif`, `1x1`, `spacer.gif`) and zero-dimension images.
  - Rejects stub articles lacking both summary and body.
  - Rejects headline/body mismatch and near-duplicate stories.

### 3. Content & Image Rights Policy Engine (Phase 3)
- **Separate Independent Rights Decisions:**
  - `evaluate_full_text_rights`: Authorizes text only for statutory US Federal Government works (17 U.S.C. § 105: `nasa.gov`, `cdc.gov`, `noaa.gov`, `whitehouse.gov`, etc.). Broad `.gov` wildcard completely removed. Commercial news publishers are strictly summary-only (`content_display_authorized = false`).
  - `evaluate_hero_image_rights`: Authorized only when image rights are verified. Rejects third-party commercial wire photos (Getty, AP, Reuters, AFP) embedded on government pages. Unauthorized hero image results in `image_url = None` in API (image-free layout).
  - `evaluate_inline_image_rights`: Evaluated independently from the hero image.
  - Directives like `ai_allow: true` or third-party CC BY links are strictly rejected as republication permissions.

### 4. Single-Page Broadsheet Reading Experience (Phase 4 & 6)
- **Editorial Reading Column:**
  - Single continuous reading column (`max-w-3xl`) with generous line height (`leading-[1.8]`).
  - Natural word wrapping on prose (`[overflow-wrap:break-word] [word-break:normal]`), eliminating unsightly mid-word hyphenation.
  - `break-all` isolated strictly to canonical external URLs in attribution rows to prevent viewport overflow.
  - Editorial serif typography (`font-serif leading-[1.2]`).
  - Single publisher attribution row (`"By [Author] · Originally published by [Publisher]"`).
  - Authorized hero image with italicized caption and uppercase credit badge via `ArticleHeroImage.tsx`.
  - Bold summary lede above body only when genuine summary exists; never fabricated.
  - Complete article body when authorized, with subheadings (`h2`/`h3`) and gold-bordered blockquotes.
  - Dignified summary-only fallback card for commercial articles (`"Read Full Article at [Publisher]"`).
  - Related editorial coverage grid.

### 5. 12-Scenario Acceptance Testing Matrix (Phase 8)

| Scenario | Description | Backend Unit Test | Live Browser / HTML Verification | Status |
| :---: | :--- | :--- | :--- | :---: |
| **1** | Authorized full-text with permitted hero image | `test_authorized_fulltext_with_hero_image` | NASA Webb Telescope story: full body + hero image + caption rendered | **PASS** |
| **2** | Authorized full-text without image | `test_authorized_fulltext_without_image` | NOAA Climate story: full body rendered in clean image-free layout | **PASS** |
| **3** | Summary-only commercial article | `test_summary_only_commercial_article` | Reuters Tech story: full text masked, summary lede + publisher CTA rendered | **PASS** |
| **4** | Non-English Unicode article | `test_non_english_unicode_article` | Bengali Dhaka story: authentic Unicode rendered without font corruption | **PASS** |
| **5** | Article with multiple paragraphs | `test_multiple_paragraphs_preserved` | CDC Health story: 4 distinct paragraphs preserved with proper margins | **PASS** |
| **6** | Article with inline image and caption | `test_inline_image_and_caption_supported` | Inline diagram and caption rendered within reading column | **PASS** |
| **7** | Article with malformed image URL | `test_malformed_image_url_filtered` | Non-HTTP/corrupt image filtered; graceful image-free fallback | **PASS** |
| **8** | Article with no summary and no body | `test_stub_article_without_summary_or_body_rejected` | Rejected by validation service; never published | **PASS** |
| **9** | Duplicate article | `test_duplicate_headline_and_url_rejected` | Canonical URL hash collision detected; duplicate rejected | **PASS** |
| **10** | Invalid JSON / schema response | `test_invalid_json_schema_response_handled` | Missing required fields handled safely without crashing pipeline | **PASS** |
| **11** | Unauthorized image (third-party wire) | `test_unauthorized_hero_image_withheld` | AP photo on CDC page withheld (`image_url = None`); image-free layout | **PASS** |
| **12** | Unauthorized commercial full text | `test_unauthorized_commercial_fulltext_masked` | Commercial body masked; `full_text = None` in public API response | **PASS** |

### 6. Verification Suite Results Summary

| Test Domain | Target / Command | Result / Metrics | Status |
| :--- | :--- | :--- | :---: |
| **Backend Test Suite** | `python -m pytest backend/tests -v` | **185 passed, 0 failed, 2 warnings** in 9.09s | **PASS** |
| **Full Text Matrix Tests** | `pytest backend/tests/test_article_full_text.py` | **17 passed, 0 failed** in 0.16s | **PASS** |
| **Frontend Static Typecheck** | `npm --prefix frontend run typecheck` | `tsc --noEmit` exited with code 0 (0 errors) | **PASS** |
| **Frontend ESLint Audit** | `npm --prefix frontend run lint` | `next lint` exited with code 0 (0 warnings, 0 errors) | **PASS** |
| **Frontend Production Build** | `npm --prefix frontend run build` | Next.js standalone build compiled 14 routes cleanly | **PASS** |
| **5-Viewport Browser Audit** | `scripts/verify_editorial_article_quality.js` | 1440px, 1024px, 768px, 390px, 360px: 0px overflow across all | **PASS** |
| **Public Endpoint Audit** | `scripts/verify_all_endpoints.py` | 100% HTTP 200 OK across health, categories, search, feeds | **PASS** |
| **Puppeteer Functional Suite**| `scripts/browser_functional_test.js` | 12/12 routes passed, 0 console errors, 0 failed requests | **PASS** |


