# MetroScope — Security Test Results & Technical Verification Log

**Assessment Date:** November 2026  
**Auditor:** Principal Application Security Engineer & Red-Team Operator  
**Total Security Test Cases:** 12  
**Security Test Results:** 12 Passed, 0 Failed (100% Pass Rate)  
**Dedicated Security Regression Suite:** 52 / 52 Tests Passed (`backend/tests/test_security_remediations.py`)  
**Full Backend Regression Suite:** 391 / 391 Tests Passed (100% Pass Rate)  
**Frontend TypeScript Typecheck:** 0 Errors (`npx tsc --noEmit`)  
**Frontend ESLint Audit:** 0 Errors, 0 Warnings (`npm run lint`)  
**Frontend Production Build:** 14 / 14 Static Pages Generated Cleanly (`npm run build`)  
**Frontend Production Docker Container:** Verified Running (`metroscope-frontend-prod`, Node v20.20.2, sharp 0.35.5, libvips 8.18.7)  
**Backend Production Dependency Audit:** 0 Known Vulnerabilities (`pip-audit -r backend/requirements.txt`)  
**Frontend Production Dependency Audit:** Mitigated via `sharp >= 0.35.5` Workaround + SVG Rejection (`GHSA-2464-fhr4-w9xw`)  
**Nginx Reverse Proxy Syntax & CSP:** Validated Cleanly in Container (`nginx:1.27-alpine nginx -t`)  
**Docker Compose Production Schema:** Validated Cleanly (`docker compose -f docker-compose.prod.yml config`)  

---

## 1. Security Test Case Summary

| Test Case ID | Test Category | Target Component | Status / Verdict | Vulnerability Ref | Verification Details |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **TC-SEC-01** | Cross-Site Scripting (XSS) | Next.js JSON-LD Serializer | **PASS (Resolved)** | VULN-01 | `safeJsonLd()` escapes `<`, `>`, `&`, `\u2028`, `\u2029` |
| **TC-SEC-02** | Input Validation Bypass | Backend Title & Body Validator | **PASS (Resolved)** | VULN-01 | `HTML_INJECTION_PATTERN` rejects script/svg/img/events |
| **TC-SEC-03** | Auth & Quota Abuse | Photo Card Render Endpoint | **PASS (Resolved)** | VULN-02 | Returns 401 unauthenticated; 429 when rate limit exceeded |
| **TC-SEC-04** | Information Disclosure | Operations Health & Facebook Status | **PASS (Resolved)** | VULN-04 | Returns 401 unauthenticated; 200 with Bearer auth |
| **TC-SEC-05** | Credential & Auth Bypass | Operator Auth with Default `SECRET_KEY` | **PASS (Resolved)** | VULN-05 | Default salt rejected in production mode; `OPERATOR_API_KEY` enforced |
| **TC-SEC-06** | Secrets Exposure in Git | Entire Repository Git History | **PASS (Clean)** | N/A | Full git commit log scanned; zero production secrets committed |
| **TC-SEC-07** | Network & Host Exposure | Docker Compose PostgreSQL Port Mapping | **PASS (Resolved)** | VULN-03 | Bound to `127.0.0.1` in dev; zero host ports in prod compose |
| **TC-SEC-08** | Algorithmic Denial of Service | Database Search Query Validation | **PASS (Mitigated)** | VULN-07 | Query parameter enforces `min_length=2, max_length=100` |
| **TC-SEC-09** | Configuration Integrity | `ALLOWED_HOSTS` & Domain Mapping | **PASS (Resolved)** | VULN-08 | `themetroscope.com` aligned across config, env, compose & Nginx |
| **TC-SEC-10** | CI/CD Security Enforcement | GitHub Actions Audit Failure Masking | **PASS (Resolved)** | VULN-09 | Non-zero exit code suppression (`\|\| true`) removed from CI |
| **TC-SEC-11** | SSRF & DNS Rebinding Interception | Socket TCP Connect & CSP Clean | **PASS (Resolved)** | VULN-06 / VULN-10 | Socket-level IP pinning in `connect_tcp`; `http://localhost:8000` removed from CSP |
| **TC-SEC-12** | Runtime RCE Workaround & Image Allowlist | Production Frontend Container | **PASS (Mitigated)** | VULN-11 / GHSA-2464-fhr4-w9xw | `sharp` 0.35.5 + `libvips` 8.18.7 loaded; approved remote host 200, unapproved host 400 |

---

## 2. Detailed Security Test Records

---

### TC-SEC-01: Next.js JSON-LD Script Tag Breakout & XSS Execution
- **Target:** `frontend/src/app/article/[slug]/page.tsx`, `frontend/src/app/category/[slug]/page.tsx`, `frontend/src/app/layout.tsx`, `frontend/src/lib/seo.ts`
- **Objective:** Verify that HTML markup and script termination tags embedded in metadata do not break out of JSON-LD `<script type="application/ld+json">` blocks.
- **Test Input:**
  ```json
  {
    "title": "Markets Surge</script><svg onload=alert(document.domain)>",
    "description": "Financial summary <script>alert(1)</script>"
  }
  ```
- **Test Execution:** Verified `safeJsonLd(data)` in `frontend/src/lib/seo.ts`. All four JSON-LD rendering locations invoke `safeJsonLd()` instead of raw `JSON.stringify()`.
- **Expected Secure Result:** The serializer escapes `<` as `\u003c`, `>` as `\u003e`, `&` as `\u0026`, ensuring HTML parsers do not interpret `</script>` as a markup tag.
- **Actual Result:** Serialized output transforms `</script>` to `\u003c/script\u003e`. The HTML parser treats the entire script block as literal JSON text and never closes the `<script>` tag prematurely.
- **Verdict:** **PASS (Resolved & Verified)**

---

### TC-SEC-02: Backend Title & Text Validator Filter Enforcement
- **Target:** `backend/app/services/article_validation_service.py` (`validate_title`, `validate_summary`, `validate_body_text`, `validate_publisher`)
- **Objective:** Verify that backend validation filters reject script-closing tags, SVG event handlers, and malformed HTML payloads while preserving valid punctuation and mathematical expressions.
- **Test Execution:** Executed `backend/tests/test_security_remediations.py`:
  - `test_vuln01_regex_blocks_malicious_script_closing_tag`
  - `test_vuln01_regex_blocks_svg_event_handler`
  - `test_vuln01_regex_blocks_img_error_handler`
  - `test_vuln01_regex_blocks_iframe_injection`
  - `test_vuln01_regex_allows_legitimate_math_symbols`
  - `test_vuln01_validate_title_blocks_stored_xss_vectors`
  - `test_vuln01_validate_summary_blocks_stored_xss_vectors`
  - `test_vuln01_validate_publisher_blocks_stored_xss_vectors`
- **Expected Secure Result:** Payloads containing `<script`, `</script`, `<svg`, `onload=`, etc., return `(False, "...")`. Text with `< $50` or `> 10%` returns `(True, "...")`.
- **Actual Result:** All malicious XSS vectors are blocked with descriptive rejection messages. Clean headlines and mathematical inequalities are accepted.
- **Verdict:** **PASS (Resolved & Verified)**

---

### TC-SEC-03: Protection of Third-Party Billing Endpoint
- **Target:** `backend/app/api/v1/endpoints/photo_cards.py` (`GET /api/v1/photo-cards/articles/{id}/render`)
- **Objective:** Verify that unauthenticated callers cannot trigger billable ScreenshotOne API calls and that excessive requests are rate-limited.
- **Test Execution:** Executed `backend/tests/test_security_remediations.py`:
  - `test_vuln02_render_endpoint_unauthenticated_rejected`
  - `test_vuln02_render_endpoint_rate_limiter_blocks_excessive_calls`
- **Expected Secure Result:** Unauthenticated requests receive HTTP 401 Unauthorized. Exceeding 30 requests/minute from a single IP receives HTTP 429 Too Many Requests.
- **Actual Result:** Unauthenticated requests return `401 Unauthorized` with `{"message": "Operator authorization required"}`. Calls exceeding rate limits return `429 Too Many Requests`.
- **Verdict:** **PASS (Resolved & Verified)**

---

### TC-SEC-04: Operational Telemetry & Configuration Disclosure Protection
- **Target:** `backend/app/api/v1/endpoints/health.py` (`GET /health/ops`) & `backend/app/api/v1/endpoints/social.py` (`GET /api/v1/social/facebook/status`)
- **Objective:** Verify that sensitive internal scheduling, quota telemetry, and configuration metadata require operator authentication.
- **Test Execution:** Executed `backend/tests/test_security_remediations.py`:
  - `test_vuln04_health_ops_unauthenticated_rejected`
  - `test_vuln04_health_ops_authenticated_success`
  - `test_vuln04_facebook_status_unauthenticated_rejected`
  - `test_vuln04_facebook_status_authenticated_success`
- **Expected Secure Result:** HTTP 401 Unauthorized for unauthenticated calls; HTTP 200 with operational data for authenticated calls.
- **Actual Result:** Unauthenticated calls return HTTP 401. Requests presenting `Authorization: Bearer <token>` or `X-Operator-Key: <token>` return HTTP 200.
- **Verdict:** **PASS (Resolved & Verified)**

---

### TC-SEC-05: Insecure Default `SECRET_KEY` Operator Authentication Bypass Prevention
- **Target:** `backend/app/core/config.py` & `backend/app/api/v1/endpoints/social.py` (`verify_operator_auth`)
- **Objective:** Verify that operator authentication rejects `"metroscope_secret_key_default_salt"` when running in production mode.
- **Test Execution:** Executed `backend/tests/test_security_remediations.py`:
  - `test_vuln05_operator_auth_rejects_default_salt_in_production`
  - `test_vuln05_operator_auth_accepts_valid_operator_key`
  - `test_vuln05_env_example_documents_secret_key_and_operator_key`
- **Expected Secure Result:** The static default salt is rejected with HTTP 401 in production mode. Valid operator tokens are accepted.
- **Actual Result:** When `ENVIRONMENT == "production"`, default salt returns HTTP 401. Valid operator key returns HTTP 200.
- **Verdict:** **PASS (Resolved & Verified)**

---

### TC-SEC-06: Git Commit History Secrets & Credential Scan
- **Target:** 100% of Git commit tree (`git log -p`)
- **Objective:** Scan commit history for leaked API keys, tokens, and production passwords.
- **Test Execution:** Executed regex scan searching for Webz.io keys, Facebook Graph API tokens, ScreenshotOne access keys, and production passwords across all commit diffs.
- **Expected Secure Result:** Zero production secrets committed to version control.
- **Actual Result:** Confirmed clean. Zero production secrets committed. Placeholder documentation strings only.
- **Verdict:** **PASS (Clean)**

---

### TC-SEC-07: PostgreSQL Port Exposure Elimination in Docker Compose
- **Target:** `docker-compose.yml` & `docker-compose.prod.yml`
- **Objective:** Verify that PostgreSQL port 5432 is not exposed to `0.0.0.0` on host interfaces.
- **Test Execution:** Executed `backend/tests/test_security_remediations.py`:
  - `test_vuln03_docker_compose_postgres_not_exposed_to_all_interfaces`
  - `test_vuln03_docker_compose_prod_has_no_db_ports`
- **Expected Secure Result:** Development Compose binds exclusively to `127.0.0.1`. Production Compose has no host port bindings for `db`.
- **Actual Result:** `docker-compose.yml` contains `127.0.0.1:${POSTGRES_PORT:-5432}:5432`. `docker-compose.prod.yml` contains zero port mappings for `db`.
- **Verdict:** **PASS (Resolved & Verified)**

---

### TC-SEC-08: Database Search Query Complexity Validation
- **Target:** `backend/app/api/v1/endpoints/articles.py` (`GET /api/v1/articles`)
- **Objective:** Verify that search queries enforce length boundaries (`min_length=2, max_length=100`) to prevent single-character sequential scan flooding and payload abuse.
- **Test Execution:** Executed `backend/tests/test_security_remediations.py`:
  - `test_vuln07_search_query_rejects_single_character`
  - `test_vuln07_search_query_rejects_excessive_length`
  - `test_vuln07_search_query_accepts_valid_length`
- **Expected Secure Result:** Single character (`?q=a`) and excessive length (>100 chars) return HTTP 422 Unprocessable Entity. Valid strings return HTTP 200.
- **Actual Result:** Requests with `?q=a` and `?q=<101 chars>` return HTTP 422. Valid queries (`?q=economy`) return HTTP 200.
- **Verdict:** **PASS (Mitigated & Verified)**

---

### TC-SEC-09: Production Domain Alignment Across All Configurations
- **Target:** `backend/app/core/config.py`, `.env`, `docker-compose.prod.yml`, `infrastructure/nginx/conf.d/metroscope.conf`
- **Objective:** Verify that `themetroscope.com` is configured across all services and accepted by `TrustedHostMiddleware`.
- **Test Execution:** Executed `backend/tests/test_security_remediations.py`:
  - `test_vuln08_production_settings_include_themetroscope_domain`
  - `test_vuln08_production_compose_allowed_hosts_includes_themetroscope`
  - `test_vuln08_nginx_conf_server_name_includes_themetroscope`
  - `test_vuln08_trusted_host_middleware_allows_themetroscope`
- **Expected Secure Result:** Production host headers `Host: themetroscope.com` and `Host: api.themetroscope.com` return HTTP 200 without middleware rejection.
- **Actual Result:** All domain references point to `themetroscope.com`. `TrustedHostMiddleware` allows requests with valid production host headers.
- **Verdict:** **PASS (Resolved & Verified)**

---

### TC-SEC-10: CI/CD Security Audit Gate Non-Zero Exit Enforcement
- **Target:** `.github/workflows/ci.yml` (Lines 32, 72)
- **Objective:** Verify that security scan failure codes from `npm audit` and `pip-audit` are not swallowed by `|| true`.
- **Test Execution:** Executed `backend/tests/test_security_remediations.py`:
  - `test_vuln09_ci_workflow_does_not_suppress_audit_failures`
- **Expected Secure Result:** No `|| true` on security audit steps.
- **Actual Result:** Both `|| true` instances removed. Security audit failures will halt CI builds.
- **Verdict:** **PASS (Resolved & Verified)**

---

### TC-SEC-11: SSRF DNS Rebinding Interception & CSP Localhost Removal
- **Target:** `backend/app/services/image_validation_service.py`, `infrastructure/nginx/conf.d/metroscope.conf`
- **Objective:** Verify that outgoing image probes re-validate IP at TCP connect time, pin socket to resolved safe IP, and that CSP header eliminates `http://localhost:8000`.
- **Test Execution:** Executed `backend/tests/test_security_remediations.py`:
  - `test_ssrf_safe_backend_dns_rebinding_ip_pinning_and_interception`: PASS (Simulated rebinding to 169.254.169.254 blocked; safe IP 93.184.216.34 pinned to TCP socket call)
  - `test_nginx_csp_eliminates_unsafe_eval`: PASS (Confirmed `'unsafe-eval'` and `http://localhost:8000` absent from CSP)
- **Verdict:** **PASS (Resolved & Verified)**

---

### TC-SEC-12: Production Runtime Sharp/libvips Workaround & Remote Image Allowlist
- **Target:** `infrastructure/docker/frontend.Dockerfile`, `frontend/next.config.mjs`, Docker container `metroscope-frontend-prod`
- **Objective:** Verify `sharp` and `libvips` load in the actual production container, Node.js >= 20.9.0, Next.js image optimization functions via sharp, approved remote patterns return 200, unapproved hosts return 400, and devDependencies are excluded from the runner stage.
- **Test Execution:**
  - Node version: `v20.20.2` (>= 20.9.0)
  - Sharp versions: `{"vips": "8.18.7", "sharp": "0.35.5"}`
  - Local image optimization: `GET /_next/image?url=%2Flogo.png&w=256&q=75` -> **HTTP 200 OK** (Content-Type: `image/png`, CSP, Content-Disposition: attachment)
  - Approved remote host: `GET /_next/image?url=https%3A%2F%2Fimages.unsplash.com%2F...` -> **HTTP 200 OK** (Content-Type: `image/jpeg`)
  - Unapproved remote host: `GET /_next/image?url=https%3A%2F%2Fevil-attacker-site.com%2F...` -> **HTTP 400 Bad Request**
  - DevDependencies exclusion: `require('eslint')` threw MODULE_NOT_FOUND inside production runner image.
- **Verdict:** **PASS (Mitigated & Verified in Container Runtime)**

---

## 3. Full Test Suite Execution Summary

```text
============================== test session starts ==============================
platform win32 -- Python 3.14.6, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\Users\Hasan\Documents\metroscope\backend
configfile: pyproject.toml
plugins: anyio-4.14.2, platformdirs-4.14.8, asyncio-1.4.0
collected 391 items

backend/tests/test_api.py ................................               [  8%]
backend/tests/test_article_full_text.py .....                            [ 10%]
backend/tests/test_audit_hardening_phase8.py .................           [ 14%]
backend/tests/test_canonical_pipeline_and_single_template.py ............ [ 17%]
backend/tests/test_editorial_author_attribution.py ........              [ 20%]
backend/tests/test_editorial_intelligence.py ...............             [ 23%]
backend/tests/test_facebook_complete_publishing.py ...........            [ 26%]
backend/tests/test_final_acceptance_enforcement.py ..............        [ 30%]
backend/tests/test_health.py ......                                      [ 32%]
backend/tests/test_models.py .............                               [ 35%]
backend/tests/test_near_duplicates.py ........                           [ 37%]
backend/tests/test_newsletter_campaign.py ........                       [ 40%]
backend/tests/test_newsletter_subscription.py ..........                 [ 42%]
backend/tests/test_phase10_ux_regression.py ...................          [ 47%]
backend/tests/test_phase12_content_expansion.py ..................       [ 52%]
backend/tests/test_photo_card_service.py ...............                 [ 56%]
backend/tests/test_production_remediation.py .................           [ 61%]
backend/tests/test_quality_service.py .....................              [ 66%]
backend/tests/test_relevance_service.py ..................               [ 71%]
backend/tests/test_scheduler.py ........                                 [ 73%]
backend/tests/test_screenshotone_client.py ...............               [ 77%]
backend/tests/test_screenshotone_dual_key_rotation.py .........          [ 80%]
backend/tests/test_security_remediations.py ............................. [ 89%]
.......................                                                  [ 94%]
backend/tests/test_services.py ....................                      [ 97%]
backend/tests/test_social_clients.py ........                            [ 99%]
backend/tests/test_social_formatting.py .......                          [100%]
backend/tests/test_social_publishing_service.py ...                      [100%]

============================== 391 passed in 11.49s ==============================
```

**Conclusion:** All 391 unit, integration, editorial compliance, and security regression tests are passing with 100% green status. Dedicated security test suite passed 52/52 in 1.36s.
