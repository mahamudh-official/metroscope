# MetroScope — Phase 8 Correction & Consolidated Verification Report

## 1. Overview of Confirmed Issues Fixed

During the Phase 8 Platform Audit, 11 defects across security, social publishing idempotency, editorial data flow, search crawling, and infrastructure integration were identified and corrected:

| Issue ID | Severity | Description | Resolution Summary |
| :--- | :--- | :--- | :--- |
| **AUDIT-01** | CRITICAL | Social publishing ambiguous HTTP success (malformed payload or missing ID) marked as `FAILED`. | Added `ambiguous: bool` to `SocialPostResult`; client adapters return `ambiguous=True`; orchestrator transitions status to `FAILED_AMBIGUOUS`, permanently excluding from automated retry. |
| **AUDIT-02** | CRITICAL | Post-dispatch database exceptions overwriting confirmed external posts with retriable `FAILED`. | Exception handler in `SocialPublishingService` checks if external call already succeeded (`result.success=True`), falling back to `RECONCILIATION_REQUIRED` / `FAILED_AMBIGUOUS` instead of `FAILED`. |
| **AUDIT-03** | HIGH | Rolling 24h social quota under-counting in-flight and ambiguous posts. | Modified `get_published_count_in_window` in `social_repository.py` to count `status.in_(["PUBLISHED", "FAILED_AMBIGUOUS", "RECONCILIATION_REQUIRED"])`. |
| **AUDIT-04** | HIGH | URL scheme injection (`javascript:`, `file:`) and stored XSS via unescaped HTML title tags. | Enforced strict `http` / `https` scheme whitelist and non-empty netloc in `normalize_url()`; added HTML tag stripping (`re.sub(r"<[^>]+>", "", title)`) in `clean_title()`. |
| **AUDIT-05** | MEDIUM | `get_article_by_slug` bypassed published status check, exposing draft/filtered records. | Added `status: Optional[str] = "published"` default filter predicate to `get_article_by_slug()` in `article_repository.py`. |
| **AUDIT-06** | MEDIUM | Search engine crawlers indexing utility routes (`/unsubscribe`, `/verify-subscription`). | Added `noIndex: true` layouts for `/unsubscribe` and `/verify-subscription`; updated `frontend/src/app/robots.ts` disallow rules. |
| **AUDIT-07** | MEDIUM | Missing `TrustedHostMiddleware` and security response headers in FastAPI backend. | Added Starlette `TrustedHostMiddleware` with `settings.ALLOWED_HOSTS` and middleware adding `X-Content-Type-Options: nosniff` and `X-Frame-Options: SAMEORIGIN`. |
| **AUDIT-08** | MEDIUM | Database TCP socket pre-flight probe failing on SQLite in-memory tests. | Updated `check_db_connection()` in `session.py` to bypass TCP socket pre-flight when SQLite driver is in use. |
| **AUDIT-09** | MEDIUM | Unsubscribe HMAC token salt coupled to database password. | Introduced dedicated `SECRET_KEY` in `Settings`; updated `generate_unsubscribe_token()` to derive HMAC from `SECRET_KEY`. |
| **AUDIT-10** | MEDIUM | Frontend Next.js SSR requests inside Docker trying external public domain rather than internal Docker backend. | Updated `getApiBaseUrl()` in `frontend/src/lib/api.ts` to prioritize `INTERNAL_API_URL` during SSR; configured `INTERNAL_API_URL: http://backend:8000/api/v1` in compose files. |
| **AUDIT-11** | LOW | Database restore validation script omitted social posts and newsletter campaigns. | Added `social_posts` and `newsletter_campaigns` count checks to `scripts/restore_postgres.sh`. |

---

## 2. Files Changed

### Backend Source Files
1. `backend/app/core/config.py`: Added `SECRET_KEY`, added `"testserver"` and `"test"` to `ALLOWED_HOSTS`, added production configuration audit check for default `SECRET_KEY`.
2. `backend/app/main.py`: Added `TrustedHostMiddleware` registration and centralized HTTP middleware injecting `X-Content-Type-Options: nosniff` and `X-Frame-Options: SAMEORIGIN`.
3. `backend/app/db/session.py`: Updated `check_db_connection` to bypass TCP socket pre-flight for SQLite dialects.
4. `backend/app/services/url_service.py`: Enforced `http` and `https` scheme validation and non-empty `netloc` requirement in `normalize_url`.
5. `backend/app/services/normalizer_service.py`: Added HTML tag stripping regex in `clean_title` to prevent stored markup injection.
6. `backend/app/repositories/article_repository.py`: Added default `status: Optional[str] = "published"` filtering in `get_article_by_slug`.
7. `backend/app/repositories/social_repository.py`: Updated `get_published_count_in_window` to include `PUBLISHED`, `FAILED_AMBIGUOUS`, and `RECONCILIATION_REQUIRED` in rolling 24-hour quota calculation.
8. `backend/app/social/base.py`: Added `ambiguous: bool = False` field to `SocialPostResult`.
9. `backend/app/social/facebook_client.py`: Returned `ambiguous=True` on malformed HTTP 200 responses or missing post ID.
10. `backend/app/social/x_client.py`: Returned `ambiguous=True` on malformed HTTP 201 responses or missing tweet ID.
11. `backend/app/social/publishing_service.py`: Handled `result.ambiguous` by recording `FAILED_AMBIGUOUS`; updated post-dispatch exception handler to preserve `RECONCILIATION_REQUIRED` / `FAILED_AMBIGUOUS` rather than retriable `FAILED`.
12. `backend/app/newsletter/service.py`: Decoupled `generate_unsubscribe_token` HMAC secret from database password to use `settings.SECRET_KEY`.

### Frontend Source Files
13. `frontend/src/lib/api.ts`: Updated `getApiBaseUrl` to check `typeof window === "undefined"` and `INTERNAL_API_URL` first for server-side rendering.
14. `frontend/src/app/robots.ts`: Added `/search`, `/unsubscribe`, and `/verify-subscription` to robots disallow list.
15. `frontend/src/app/unsubscribe/layout.tsx`: Created layout exporting `noIndex: true` metadata.
16. `frontend/src/app/verify-subscription/layout.tsx`: Created layout exporting `noIndex: true` metadata.

### Infrastructure & Script Files
17. `docker-compose.prod.yml`: Added `INTERNAL_API_URL: http://backend:8000/api/v1` to `frontend` service environment.
18. `docker-compose.yml`: Added `INTERNAL_API_URL: http://backend:8000/api/v1` to `frontend` service environment.
19. `scripts/restore_postgres.sh`: Added `social_posts` and `newsletter_campaigns` entity counts to post-restore validation query.

---

## 3. Migrations Added or Modified

No schema alterations or new columns were required. Existing database columns (`status`, `canonical_url_hash`, `verification_token_hash`, `unsubscribe_token_hash`, `attempt_count`, `last_error`, `recovered_at`, `recovery_notes`) fully accommodate all hardened states (`FAILED_AMBIGUOUS`, `RECONCILIATION_REQUIRED`). Existing Alembic migrations `0001` through `0008` remain completely backward and forward compatible.

---

## 4. Regression Tests Added

A dedicated regression test suite was implemented in `backend/tests/test_audit_hardening_phase8.py` covering:

1. `test_url_normalization_scheme_security`: Verifies rejection of `javascript:`, `file:`, `data:`, and `ftp:` schemes.
2. `test_clean_title_strips_html_tags`: Verifies removal of `<script>`, `<b>`, and other HTML tags from headlines.
3. `test_facebook_malformed_200_returns_ambiguous`: Confirms Facebook client returns `ambiguous=True` on malformed HTTP 200.
4. `test_x_malformed_201_returns_ambiguous`: Confirms X client returns `ambiguous=True` on HTTP 201 missing `data.id`.
5. `test_publishing_service_transitions_ambiguous_to_failed_ambiguous`: Confirms ambiguous results transition to `FAILED_AMBIGUOUS` and are excluded from subsequent publishing runs.
6. `test_publishing_service_preserves_post_dispatch_success`: Verifies database errors following successful API dispatch transition to `RECONCILIATION_REQUIRED` rather than retriable `FAILED`.
7. `test_quota_counts_ambiguous_and_reconciliation_records`: Confirms rolling 24-hour quota accounts for `PUBLISHED`, `FAILED_AMBIGUOUS`, and `RECONCILIATION_REQUIRED` records.
8. `test_get_article_by_slug_filters_unpublished`: Confirms draft/archived articles are not returned by default slug queries.
9. `test_security_headers_present`: Verifies FastAPI responses include `X-Content-Type-Options: nosniff` and `X-Frame-Options: SAMEORIGIN`.
10. `test_unsubscribe_hmac_uses_secret_key`: Verifies deterministic HMAC token generation using application secret key.

---

## 5. Final Consolidated Test Results

### Backend Test Suite
- **Command**: `python -m pytest backend`
- **Result**: **133 passed, 0 failed, 2 warnings** in 3.65s.
- **Coverage**: Full test execution across models, API endpoints, GDELT client, ingestion pipeline, quality scoring, relevance filtering, editorial intelligence, deduplication, social clients, social formatter, social publishing orchestrator, social scheduler, newsletter subscription, newsletter campaign dispatch, and Phase 8 security hardening.

### Frontend Quality Gates
- **TypeScript Typecheck**:
  - **Command**: `cd frontend; npm run typecheck`
  - **Result**: **PASSED** (0 errors).
- **ESLint**:
  - **Command**: `cd frontend; npm run lint`
  - **Result**: **PASSED** (✔ No ESLint warnings or errors).
- **Production Build**:
  - **Command**: `cd frontend; npm run build`
  - **Result**: **PASSED** (Next.js 14.2.35 standalone build, all 14 routes compiled and statically generated).

### Infrastructure Validation
- **Docker Compose (Dev)**: `docker compose config -q` -> **PASSED**.
- **Docker Compose (Prod)**: `docker compose -f docker-compose.prod.yml config -q` -> **PASSED**.
- **Container Memory Allocation**: 1,408 MB total container limit strictly validated against the approved 2 GiB `t3.small` operational budget.

---

## 6. Remaining Known Issues

None within the approved platform software scope. All identified implementation defects and security risks have been corrected.

---

## 7. Required Manual Actions for Production Deployment

Before executing the automated deployment on AWS EC2, the operator must complete the following standard credential configuration tasks:

1. **Environment File Generation**:
   - Copy `.env.production.template` to `.env` on the EC2 host (`/opt/metroscope/.env`).
   - Generate a cryptographically strong PostgreSQL password: `openssl rand -hex 24`.
   - Generate a strong application secret key: `openssl rand -hex 32` and set `SECRET_KEY=...`.
2. **Social Publishing Credentials (When Ready to Go Live)**:
   - For Facebook: Obtain Page Access Token with `pages_manage_posts` permission and configure `FACEBOOK_PAGE_ID` and `FACEBOOK_PAGE_ACCESS_TOKEN`.
   - For X: Obtain OAuth 1.0a User Context credentials with read/write access and configure `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, and `X_ACCESS_TOKEN_SECRET`.
   - Set `SOCIAL_DRY_RUN=false` and `SOCIAL_PUBLISHING_ENABLED=true` only after verifying credentials.
3. **Email SMTP Credentials**:
   - Configure production SMTP provider credentials (e.g. SendGrid or Amazon SES) in `.env`.
   - Set `EMAIL_DRY_RUN=false` only after verifying deliverability and DNS records (SPF, DKIM, DMARC).
4. **SSL / TLS Certificate Issuance**:
   - Point DNS A records for `metroscope.news` and `www.metroscope.news` to the EC2 Elastic IP.
   - Run `certbot certonly --webroot -w /var/www/certbot -d metroscope.news -d www.metroscope.news`.
   - Uncomment the HTTPS server block in `infrastructure/nginx/conf.d/metroscope.conf` and reload Nginx.

---

## 8. Production Readiness Assessment

The MetroScope codebase is hardened, architecturally consistent, resilient against worker crashes and ambiguous external outcomes, and fully compliant with all security, editorial, and resource constraints for deployment on AWS EC2 `t3.small`.
