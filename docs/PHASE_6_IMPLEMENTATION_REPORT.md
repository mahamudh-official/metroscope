# METROSCOPE — PHASE 6 IMPLEMENTATION REPORT
## Email Subscription & Newsletter Delivery Subsystem

**Project:** MetroScope — Automated US & Global News Discovery Platform  
**Phase:** Phase 6 — Email Subscription & Newsletter Delivery  
**Date:** 2026-11-08  
**Status:** **COMPLETE — ALL OBJECTIVES VERIFIED (120/120 TESTS PASSING)**  

---

## 1. Executive Summary

Phase 6 implements an end-to-end email subscription and automated newsletter delivery system for MetroScope. Designed for readers who want to receive curated news intelligence without creating user accounts, the system adheres strictly to the project constraints: zero user accounts, zero password storage, zero full-text scraping, strict CAN-SPAM compliance, cryptographically secured double opt-in verification, and zero external message brokers.

All components are configured for deployment on an AWS EC2 `t3.small` instance (2 vCPU, 2 GB RAM) with safe default dry-run mode (`EMAIL_DRY_RUN=true`), standard library SMTP delivery via thread dispatch, and APScheduler background automation.

---

## 2. Architecture & Design

```
+---------------------------------------------------------------------------------+
|                               Next.js 14 Frontend                               |
|                                                                                 |
|  SiteFooter Form           /verify-subscription                 /unsubscribe    |
|  [email] -> Submit            ?token=<raw_token>             ?token=<raw_token> |
+-----------------------+----------------------+-----------------------+----------+
                        |                      |                       |
                        v                      v                       v
+---------------------------------------------------------------------------------+
|                                FastAPI Backend                                  |
|                                                                                 |
|  POST /subscribe            GET /verify                    GET /unsubscribe     |
|         |                          |                               |            |
|         v                          v                               v            |
|  +---------------------------------------------------------------------------+  |
|  |                 NewsletterSubscriptionService                             |  |
|  |  - normalize_email()                                                      |  |
|  |  - hash_token() (SHA-256)                                                 |  |
|  |  - generate_unsubscribe_token() (HMAC-SHA256)                             |  |
|  |  - Expiration enforcement (24 hours)                                      |  |
|  |  - Rate limiting & duplicate prevention                                   |  |
|  +---------------------------------------------------------------------------+  |
+------------------------------------+--------------------------------------------+
                                     |
                                     v
+---------------------------------------------------------------------------------+
|                        PostgreSQL 16 (Alembic 0008)                             |
|                                                                                 |
|  email_subscribers           newsletter_campaigns     newsletter_deliveries     |
|  - email_normalized (UQ)     - scheduled_for          - campaign_id (FK)        |
|  - verification_token_hash   - status                 - subscriber_id (FK)      |
|  - unsubscribe_token_hash    - article_ids (JSON)     - status (pending/sent)   |
|  - status (pending/active)   - delivered/failed_count - UQ(camp_id, sub_id)     |
+------------------------------------+--------------------------------------------+
                                     ^
                                     |
+------------------------------------+--------------------------------------------+
|                         APScheduler Background Worker                           |
|                                                                                 |
|  deliver_newsletter_campaign_job (06:00 UTC daily cron, overlap lock)          |
|  +---------------------------------------------------------------------------+  |
|  |                 NewsletterCampaignService                                 |  |
|  |  - select_curated_articles (quality_score >= 70, breaking/trending 1st)   |  |
|  |  - create_daily_campaign (daily idempotent deduplication)                 |  |
|  |  - deliver_campaign (batch dispatch via SMTPEmailProvider/to_thread)      |  |
|  +---------------------------------------------------------------------------+  |
+------------------------------------+--------------------------------------------+
                                     |
                                     v
+---------------------------------------------------------------------------------+
|                                 SMTP Delivery                                   |
|  - SMTPEmailProvider (standard library smtplib in worker thread)                |
|  - EMAIL_DRY_RUN=true by default (zero accidental outbound transmissions)       |
|  - Multipart HTML & Plain Text templates with MetroScope branding               |
+---------------------------------------------------------------------------------+
```

---

## 3. Database Models & Schema Migration

Alembic revision `0008_email_newsletter` was created and applied against live PostgreSQL (Port 5433). Both upgrade and downgrade reversibility have been validated.

### A. Tables Created

1. **`email_subscribers`**:
   - `id`: Integer primary key, autoincrement.
   - `email`: VARCHAR(255), original user-submitted string.
   - `email_normalized`: VARCHAR(255), lowercase trimmed unique index.
   - `status`: VARCHAR(32), indexed (`"pending"`, `"active"`, `"unsubscribed"`).
   - `verification_token_hash`: VARCHAR(64), nullable, indexed (SHA-256 digest of secret token).
   - `verification_sent_at`: DateTime(timezone=True), nullable.
   - `verification_expires_at`: DateTime(timezone=True), nullable.
   - `verified_at`: DateTime(timezone=True), nullable.
   - `unsubscribe_token_hash`: VARCHAR(64), unique, indexed (SHA-256 digest of unsubscribe token).
   - `unsubscribed_at`: DateTime(timezone=True), nullable.
   - `created_at` / `updated_at`: DateTime(timezone=True) via `TimestampMixin`.

2. **`newsletter_campaigns`**:
   - `id`: Integer primary key, autoincrement.
   - `subject`: VARCHAR(255), not nullable.
   - `scheduled_for`: DateTime(timezone=True), indexed, not nullable.
   - `sent_at`: DateTime(timezone=True), nullable.
   - `status`: VARCHAR(32), indexed (`"draft"`, `"sending"`, `"sent"`, `"failed"`).
   - `article_ids`: JSON list of included `NewsArticle.id` integers.
   - `recipient_count`: Integer default 0.
   - `delivered_count`: Integer default 0.
   - `failed_count`: Integer default 0.
   - `created_at` / `updated_at`: DateTime(timezone=True).

3. **`newsletter_deliveries`**:
   - `id`: Integer primary key, autoincrement.
   - `campaign_id`: Integer, ForeignKey to `newsletter_campaigns.id` with `CASCADE` delete.
   - `subscriber_id`: Integer, ForeignKey to `email_subscribers.id` with `CASCADE` delete.
   - `status`: VARCHAR(32), indexed (`"pending"`, `"sent"`, `"failed"`, `"bounced"`).
   - `error_message`: Text, nullable.
   - `sent_at`: DateTime(timezone=True), nullable.
   - `created_at` / `updated_at`: DateTime(timezone=True).
   - `UniqueConstraint("campaign_id", "subscriber_id", name="uq_campaign_subscriber")`: Guarantees that a subscriber can never receive duplicate emails for the same campaign.

---

## 4. Security & Cryptographic Token Architecture

| Mechanism | Implementation | Benefit |
| :--- | :--- | :--- |
| **Email Normalization** | `normalize_email(email)`: trims whitespace and lowercases before comparison or indexing. | Eliminates duplicate accounts caused by casing (`User@Domain.Com` vs `user@domain.com`). |
| **Verification Token Hashing** | Raw 32-byte URL-safe token generated via `secrets.token_urlsafe(32)`. Only `hashlib.sha256(token).hexdigest()` stored in database. | Zero-knowledge token storage. Database leak cannot compromise reader verification links. |
| **One-Click Unsubscribe Tokens** | Derived via `hmac.new(secret, f"metroscope-unsub:{norm_email}".encode(), sha256).hexdigest()`. Database stores only `sha256(hmac)`. | Readers can unsubscribe with 1 click without needing accounts. Attacker with database access cannot compute the unsubscribe token. |
| **Token Expiration** | 24-hour expiration window (`VERIFICATION_TOKEN_EXPIRE_HOURS=24`). | Stale verification links automatically expire. |
| **One-Time Token Invalidation** | `verification_token_hash` is set to `None` upon successful verification. | Prevents replay attacks on verified subscriptions. |
| **Rate Limiting** | Evaluates subscription count over past hour. Throttles bursts. | Mitigates list bombing and email spam abuse. |

---

## 5. Email Delivery & Templates

### A. Provider Abstraction
- **`EmailProvider` ABC**: Defined in [`provider.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/newsletter/provider.py).
- **`SMTPEmailProvider`**: Utilizes standard library `smtplib` and `email.message.EmailMessage`. Non-blocking execution achieved via `asyncio.to_thread` dispatch. Supports TLS and SMTP authentication.
- **`EMAIL_DRY_RUN=True` (Default)**: Logs delivery intent (recipient, subject, payload byte length) without opening external sockets. Prevents accidental emails in test and staging environments.
- **`MockEmailProvider`**: In-memory test spy for deterministic unit and failure testing.

### B. Responsive Templates
- Designed in MetroScope branding:
  - Deep Navy header: `#0B192C`
  - Gold accent: `#E5A93C`
  - High-contrast card layouts with category badges, publisher source attribution, and direct article links.
  - CAN-SPAM compliant footer with one-click unsubscribe URL, sender identity (`MetroScope News`), and privacy policy link.
  - Strict HTML escaping (`html.escape`) on all dynamic publisher titles and descriptions to prevent XSS and email rendering injection.
  - Full plain-text alternative included in every multipart message.

---

## 6. Curated Newsletter Engine & Scheduling

- **Editorial Curation Rules**:
  - Only published articles (`status == "published"`).
  - High editorial standard: `quality_score >= 70.0`.
  - Prioritization: `is_breaking.desc(), is_trending.desc(), quality_score.desc(), published_at.desc()`.
  - Recency window: 48 hours.
  - Recency deduplication: Excludes stories included in campaigns over the prior 48 hours.
- **Campaign Deduplication**:
  - `create_daily_campaign()` checks if a campaign was already generated for today's UTC calendar date. If so, returns existing campaign without duplicating.
- **APScheduler Integration**:
  - Registered in [`backend/app/workers/scheduler.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/workers/scheduler.py).
  - Cron trigger: `CronTrigger(hour=6, minute=0)` (06:00 UTC daily).
  - Lock protection: `_newsletter_campaign_lock = asyncio.Lock()` ensures that overlapping worker triggers never double-send.

---

## 7. Next.js Frontend Integration

1. **Footer Subscription Form** ([`SiteFooter.tsx`](file:///c:/Users/Hasan/Documents/metroscope/frontend/src/components/SiteFooter.tsx)):
   - Connected to `/api/v1/newsletter/subscribe`.
   - Dynamic UI states:
     - **Submitting**: Spinner with disabled button.
     - **Verification Sent**: Checkmark card asking reader to check inbox with "Subscribe another email" reset button.
     - **Already Subscribed**: Information card indicating the email is already registered.
     - **Error / Network Issue**: Inline alert badge displaying the specific failure reason.
2. **Verification Page** ([`/verify-subscription`](file:///c:/Users/Hasan/Documents/metroscope/frontend/src/app/verify-subscription/page.tsx)):
   - Reads `?token=` parameter.
   - Shows loading verification state.
   - On success: green badge with "Explore Today's News" button.
   - On expired/invalid: error badge with "Request a New Link" action.
3. **Unsubscribe Page** ([`/unsubscribe`](file:///c:/Users/Hasan/Documents/metroscope/frontend/src/app/unsubscribe/page.tsx)):
   - Reads `?token=` parameter.
   - Confirms removal from newsletter list with "Re-subscribe" and "Return to Home" options.

---

## 8. Comprehensive Test & Verification Results

### A. Backend Pytest Suite
```
tests\test_api.py ......                                                 [  5%]
tests\test_editorial_intelligence.py ........                            [ 11%]
tests\test_gdelt_client.py ...                                           [ 14%]
tests\test_health.py ..                                                  [ 15%]
tests\test_ingestion.py ...                                              [ 18%]
tests\test_models.py .....                                               [ 22%]
tests\test_near_duplicates.py ......                                     [ 27%]
tests\test_newsletter_campaign.py ......                                 [ 32%]
tests\test_newsletter_subscription.py ........                           [ 39%]
tests\test_quality_service.py ....                                       [ 42%]
tests\test_relevance_service.py ............                             [ 52%]
tests\test_scheduler.py .                                                [ 53%]
tests\test_services.py ..........                                        [ 61%]
tests\test_social_clients.py ......................                      [ 80%]
tests\test_social_formatting.py ............                             [ 90%]
tests\test_social_publishing_service.py .......                          [ 95%]
tests\test_social_scheduler.py ....                                      [ 99%]
tests\test_worker.py .                                                   [100%]

======================= 120 passed, 2 warnings in 2.82s =======================
```
- **Total Tests:** **120 passed out of 120** (14 new Phase 6 tests).
- Zero test failures, zero regressions across Phases 1–5.1.

### B. Frontend Verification
- `npm run typecheck` (`tsc --noEmit`): **Passed with 0 errors**.
- `npm run lint` (`next lint`): **Passed with 0 warnings and 0 errors**.
- `npm run build` (`next build`): **Succeeded across all 14 routes** including `/verify-subscription` and `/unsubscribe`.

### C. Database Migration Verification
- Alembic HEAD: **`0008_email_newsletter`** verified on live PostgreSQL (Port 5433).
- Downgrade to `0007_stale_recovery` and upgrade to `0008_email_newsletter` tested successfully.

### D. Docker Compose Verification
- `docker compose config`: **Passed schema validation** with all Phase 6 environment variables mapped and container memory budget preserved (1,408 MB total container memory limit).

---

## 9. Deliverables & Modified Files

| Category | File | Description |
| :--- | :--- | :--- |
| **Config & Environment** | [`backend/app/core/config.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/core/config.py) | Added SMTP, dry run, and newsletter schedule settings |
| | [`.env.example`](file:///c:/Users/Hasan/Documents/metroscope/.env.example) | Added Phase 6 configuration keys |
| | [`docker-compose.yml`](file:///c:/Users/Hasan/Documents/metroscope/docker-compose.yml) | Added Phase 6 environment variables to backend & worker |
| | [`.github/workflows/ci.yml`](file:///c:/Users/Hasan/Documents/metroscope/.github/workflows/ci.yml) | Added `EMAIL_DRY_RUN` to backend CI environment |
| **Database & Migration** | [`backend/app/models/newsletter.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/newsletter.py) | `EmailSubscriber`, `NewsletterCampaign`, `NewsletterDelivery` |
| | [`backend/app/models/__init__.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/models/__init__.py) | Exported newsletter models |
| | [`backend/alembic/versions/20261108_0008_email_newsletter.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/alembic/versions/20261108_0008_email_newsletter.py) | Alembic migration 0008 |
| | [`backend/app/repositories/newsletter_repository.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/repositories/newsletter_repository.py) | Repository operations for subscribers, campaigns, deliveries |
| **Newsletter Core** | [`backend/app/newsletter/provider.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/newsletter/provider.py) | `EmailProvider`, `SMTPEmailProvider`, `MockEmailProvider` |
| | [`backend/app/newsletter/templates.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/newsletter/templates.py) | Verification, daily briefing, and unsubscribe HTML & text templates |
| | [`backend/app/newsletter/service.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/newsletter/service.py) | Double opt-in registration, SHA-256 token hashing, unsubscription |
| | [`backend/app/newsletter/campaign_service.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/newsletter/campaign_service.py) | Article curation, campaign deduplication, and batch delivery |
| | [`backend/app/newsletter/scheduler.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/newsletter/scheduler.py) | Scheduled job with overlap lock |
| | [`backend/app/newsletter/__init__.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/newsletter/__init__.py) | Package exports |
| **API & Scheduler** | [`backend/app/schemas/newsletter.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/schemas/newsletter.py) | Pydantic v2 schemas for newsletter endpoints |
| | [`backend/app/api/v1/endpoints/newsletter.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/api/v1/endpoints/newsletter.py) | `/subscribe`, `/verify`, `/unsubscribe`, `/status` endpoints |
| | [`backend/app/api/v1/api.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/api/v1/api.py) | Registered `/newsletter` router |
| | [`backend/app/workers/scheduler.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/app/workers/scheduler.py) | Registered daily briefing cron job |
| **Frontend** | [`frontend/src/lib/api.ts`](file:///c:/Users/Hasan/Documents/metroscope/frontend/src/lib/api.ts) | Newsletter client API methods |
| | [`frontend/src/components/SiteFooter.tsx`](file:///c:/Users/Hasan/Documents/metroscope/frontend/src/components/SiteFooter.tsx) | Interactive newsletter form with state machine |
| | [`frontend/src/app/verify-subscription/page.tsx`](file:///c:/Users/Hasan/Documents/metroscope/frontend/src/app/verify-subscription/page.tsx) | Double opt-in confirmation page |
| | [`frontend/src/app/unsubscribe/page.tsx`](file:///c:/Users/Hasan/Documents/metroscope/frontend/src/app/unsubscribe/page.tsx) | One-click unsubscribe confirmation page |
| **Test Suites** | [`backend/tests/test_newsletter_subscription.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/tests/test_newsletter_subscription.py) | 8 unit/integration tests for subscription & verification |
| | [`backend/tests/test_newsletter_campaign.py`](file:///c:/Users/Hasan/Documents/metroscope/backend/tests/test_newsletter_campaign.py) | 6 unit/integration tests for curation, campaign, delivery |

---

## 10. Conclusion & Readiness

MetroScope Phase 6 is **fully implemented and verified**. All requirements—including double opt-in verification, SHA-256 token hashing, one-click unsubscription, automated editorial briefing generation, safe SMTP dry-run mode, APScheduler automation, and Next.js frontend pages—are operational with 100% test passage. The codebase remains within AWS EC2 `t3.small` resource limits with zero reader account overhead.
