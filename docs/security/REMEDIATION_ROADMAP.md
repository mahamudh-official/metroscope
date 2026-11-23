# MetroScope — Security Remediation Roadmap

**Target Platform:** MetroScope News Aggregation & Publication System  
**Auditor:** Principal Application Security Engineer & Red-Team Operator  
**Date:** November 2026  
**Status:** Phase P0 Blockers 100% Remediated & Verified  

---

## Remediation Priority Matrix

| Phase | Priority Level | Target Timeline | Target Vulnerabilities | Deployment Status | Progress |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **Phase P0** | **Critical (Blockers)** | **Before Production Release** | VULN-01, VULN-02, VULN-03, VULN-08 | **DEPLOYMENT UNBLOCKED** | **100% Complete** |
| **Phase P1** | **High** | Within 7 Days of Deployment | VULN-04, VULN-05, VULN-07 | Completed Early in Batch | **100% Complete** |
| **Phase P2** | **Medium** | Within 30 Days of Deployment | VULN-06, VULN-09, VULN-10 | VULN-06, 09, 10 Completed Early | **100% Complete** |
| **Phase P3** | **Low / Operational** | Ongoing / Q1 Roadmap | Secret Rotation, SIEM Alerting | Post-Launch Operations | Pending Launch |

---

## Phase P0: Pre-Deployment Blockers (Completed & Verified)

All Phase P0 deployment blockers have been fully resolved, regression tested, and verified.

### 1. Fix Stored XSS in JSON-LD Structured Data (VULN-01) — [COMPLETED]
- **Status:** **Resolved & Verified**
- **Implemented Changes:**
  1. Frontend: Created `safeJsonLd(data: unknown): string` in `frontend/src/lib/seo.ts` which escapes `<`, `>`, `&`, `\u2028`, and `\u2029`. Deployed across all JSON-LD rendering points (`layout.tsx`, `article/[slug]/page.tsx`, `category/[slug]/page.tsx`).
  2. Backend: Added `HTML_INJECTION_PATTERN` in `backend/app/services/article_validation_service.py` rejecting script tags (`<script`, `</script`), HTML tags (`<svg`, `<img>`, `<iframe>`), and event handlers (`onload=`, `onerror=`) across `validate_title`, `validate_summary`, `validate_body_text`, and `validate_publisher`. Standard math expressions (`< $50`, `> 10%`) remain valid.
- **Verification:** 9 dedicated security regression tests passing in `backend/tests/test_security_remediations.py`. Frontend TypeScript and ESLint passing cleanly.

### 2. Protect the ScreenshotOne Render Endpoint (VULN-02) — [COMPLETED]
- **Status:** **Resolved & Verified**
- **Implemented Changes:**
  1. Added `is_operator: bool = Depends(verify_operator_auth)` and route dependency `verify_operator_auth` to `GET /api/v1/photo-cards/articles/{article_id}/render` in `backend/app/api/v1/endpoints/photo_cards.py`.
  2. Implemented `check_render_rate_limit(client_ip)` in-memory rate limiter enforcing a maximum of 30 render requests per minute per IP, returning HTTP 429 upon exceedance.
- **Verification:** Asserted HTTP 401 for unauthenticated calls and HTTP 429 for rate limit exceedance in `test_security_remediations.py`.

### 3. Close PostgreSQL Port Exposure in Docker Compose (VULN-03) — [COMPLETED]
- **Status:** **Resolved & Verified**
- **Implemented Changes:**
  1. Updated `docker-compose.yml` to bind port 5432 strictly to loopback: `127.0.0.1:${POSTGRES_PORT:-5432}:5432`.
  2. Confirmed `docker-compose.prod.yml` has **zero** host port mappings for the `db` service. Database containers communicate exclusively over internal network `metroscope_net`.
- **Verification:** Verified compose configuration files in `test_security_remediations.py` and validated schema via `docker compose -f docker-compose.prod.yml config`.

### 4. Align Domain Names & `ALLOWED_HOSTS` Configuration (VULN-08) — [COMPLETED]
- **Status:** **Resolved & Verified**
- **Implemented Changes:**
  1. Updated `backend/app/core/config.py`: Added `themetroscope.com`, `www.themetroscope.com`, `api.themetroscope.com` to default `ALLOWED_HOSTS` and `BACKEND_CORS_ORIGINS`. Changed default `SITE_URL` to `https://themetroscope.com`.
  2. Updated `.env` and `docker-compose.prod.yml` to reflect `themetroscope.com`.
  3. Updated `infrastructure/nginx/conf.d/metroscope.conf`: Updated all `server_name` directives and SSL certificate paths to `themetroscope.com`.
- **Verification:** Verified `TrustedHostMiddleware` allows requests with `Host: themetroscope.com` in `test_security_remediations.py`.

---

## Phase P1: Immediate Post-Launch Hardening (Completed Early in Batch)

### 1. Protect Internal Telemetry and Scheduler Health (VULN-04) — [COMPLETED]
- **Status:** **Resolved & Verified**
- **Implemented Changes:** Attached `dependencies=[Depends(verify_operator_auth)]` to `GET /health/ops` in `health.py` and `GET /api/v1/social/facebook/status` in `social.py`.
- **Verification:** Asserted HTTP 401 for unauthenticated calls and HTTP 200 for authenticated operator calls in `test_security_remediations.py`.

### 2. Disallow Default Fallback `SECRET_KEY` in Production (VULN-05) — [COMPLETED]
- **Status:** **Resolved & Verified**
- **Implemented Changes:** Updated `verify_operator_auth` in `social.py` to explicitly reject `"metroscope_secret_key_default_salt"` when `ENVIRONMENT == "production"`. Added dedicated `OPERATOR_API_KEY` setting and updated `.env.example`.
- **Verification:** Tested operator auth token rejection and acceptance in `test_security_remediations.py`.

### 3. Mitigate Database DoS on Search Queries (VULN-07) — [COMPLETED]
- **Status:** **Mitigated & Verified**
- **Implemented Changes:** Added query constraints `min_length=2, max_length=100` to query parameter `q` in `backend/app/api/v1/endpoints/articles.py`.
- **Verification:** Tested HTTP 422 validation rejections for single-character and excessive-length search strings in `test_security_remediations.py`.

---

## Phase P2: Defense-in-Depth & Platform Hardening (Partially Completed Early)

### 1. Enforce CI/CD Security Audit Gates (VULN-09) — [COMPLETED]
- **Status:** **Resolved & Verified**
- **Implemented Changes:** Removed `|| true` from lines 32 and 72 in `.github/workflows/ci.yml`. Non-zero exit codes from `npm audit` and `pip-audit` will correctly fail the CI build.
- **Verification:** Verified workflow file content in `test_security_remediations.py`.

### 2. Implement Strict Content Security Policy (CSP) (VULN-10) — [COMPLETED]
- **Status:** **Resolved & Verified**
- **Implemented Changes:** Added strict CSP header in `infrastructure/nginx/conf.d/metroscope.conf`. Removed `'unsafe-eval'` and removed `http://localhost:8000` from `connect-src`. Verified syntax in `nginx:1.27-alpine`.
- **Verification:** Verified CSP header presence and absence of unsafe directives in `test_security_remediations.py`.

### 3. Harden SSRF Filter Against DNS Rebinding (VULN-06) — [COMPLETED & VERIFIED]
- **Status:** **Resolved & Verified**
- **Implemented Changes:** Implemented `SSRFSafeAsyncBackend` and `SSRFSafeSyncBackend` custom transport backends in `image_validation_service.py` intercepting `connect_tcp` at the socket level. Enforces ports `{443, 80}`, re-validates resolved IPs, and directly binds the outgoing TCP socket to the validated safe IP, completely eliminating the TOCTOU DNS rebinding window. Added regression test asserting simulated DNS rebinding is blocked.
- **Defense-in-Depth:** Enforce AWS IMDSv2 with `http-put-response-hop-limit 1` during host provisioning.

---

## Phase P3: Long-Term Security Operations & Framework Upgrades

1. **Next.js 15 App Router Migration (VULN-11):** Migrate from Next.js 14.2.35 to Next.js 15.5.28+ by updating App Router page components to async `params` and `searchParams`. (Current deployment is fully secured via `sharp >= 0.35.5` + SVG rejection).
2. **Multi-Worker Distributed Rate Limiting:** Transition from in-memory rate limiting to Redis-backed distributed token bucket if FastAPI backend scales beyond a single worker process.
3. **Automated Secret Rotation:** Implement a 90-day rotation schedule for third-party API keys (Webz.io, ScreenshotOne, Facebook Page Tokens).
4. **Centralized Log Monitoring & Alerting:** Ship container logs to AWS CloudWatch or Grafana Loki with automated alert triggers on HTTP 5xx spikes and rate-limiting rejections.
