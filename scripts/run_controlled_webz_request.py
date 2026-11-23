"""MetroScope Controlled Real Webz.io Request Runner
Executes exactly ONE controlled real request to Webz.io News API.
Saves sanitized raw response sample, validates schema, applies independent rights,
and persists eligible articles to PostgreSQL.
"""
import asyncio
import datetime
import json
import os
import sys
from pathlib import Path
from decimal import Decimal

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.db.session import async_session_factory
from app.services.budget_service import BudgetProtectionService
from app.services.webz_ingestion_service import WebzIngestionService
from app.integrations.webz.client import WebzClient, CONFIRMED_QUERY

async def main():
    print("=" * 80)
    print("METROSCOPE — CONTROLLED REAL WEBZ.IO API INGESTION RUNNER")
    print("=" * 80)

    # 1. Verify Configuration & Key Presence
    if not settings.WEBZ_IO_API_KEY or not settings.WEBZ_IO_API_KEY.strip():
        print("[ERROR] WEBZ_IO_API_KEY is not set or empty in environment. Aborting.")
        sys.exit(1)

    print(f"Base URL:         {settings.WEBZ_IO_BASE_URL}")
    print(f"Endpoint:         {settings.WEBZ_IO_ENDPOINT}")
    print(f"Query:            {CONFIRMED_QUERY}")
    print(f"Parameters:       sort=crawled, size=10, format=json, webz_reporter=true, includeSyndicated=false, allowNewsHistory=false")
    print(f"Monthly Credit:   ${settings.WEBZ_IO_MONTHLY_CREDIT}")
    print(f"Ceiling:          ${settings.WEBZ_IO_COLLECTION_CEILING}")
    print(f"Reserve Floor:    ${settings.WEBZ_IO_PROTECTED_RESERVE}")
    print(f"Estimated Cost:   ${settings.WEBZ_IO_ESTIMATED_COST_PER_REQUEST}")
    print(f"Token Configured: True (Length: {len(settings.WEBZ_IO_API_KEY)}, Token Redacted)")
    print("-" * 80)

    async with async_session_factory() as db:
        # 2. Budget Preflight
        budget_service = BudgetProtectionService()
        preflight = await budget_service.preflight_check(db=db)
        summary = await budget_service.get_period_summary(db=db)
        print(f"[BUDGET PREFLIGHT] Allowed: {preflight.allowed}")
        print(f"  - Current Spend:        ${summary.total_spent:.4f}")
        print(f"  - Monthly Ceiling:      ${summary.collection_ceiling:.4f}")
        print(f"  - Remaining Allowance:  ${summary.remaining_allowance:.4f}")
        print(f"  - Emergency Reserve:    ${summary.protected_reserve:.4f}")
        print(f"  - Estimated Cost:       ${preflight.estimated_cost:.4f}")

        if not preflight.allowed:
            print(f"[ABORT] Budget check failed: {preflight.stop_reason}")
            sys.exit(1)

        # 3. Controlled API Request & Raw Capture Wrapper
        client = WebzClient(
            api_key=settings.WEBZ_IO_API_KEY,
            base_url=settings.WEBZ_IO_BASE_URL,
            endpoint=settings.WEBZ_IO_ENDPOINT,
        )

        original_fetch = client.fetch_news_articles
        captured_response = None

        async def wrapped_fetch(*args, **kwargs):
            nonlocal captured_response
            print(f"\n[DISPATCH] Executing exactly 1 real API request to {client.base_url}{client.endpoint}...")
            resp = await original_fetch(*args, **kwargs)
            captured_response = resp
            return resp

        client.fetch_news_articles = wrapped_fetch

        # 4. Execute Ingestion via WebzIngestionService
        ingestion_service = WebzIngestionService(client=client, budget_service=budget_service)
        run_stats = await ingestion_service.run_category_collection(
            db=db,
            category="business",
            job_name="controlled_webz_collection",
            freshness_hours=24,
            target_articles=10,
        )

        print("\n" + "=" * 80)
        print("API CALL EXECUTION RESULT")
        print("=" * 80)
        print(f"Status:       {run_stats.get('status')}")
        print(f"Fetched:      {run_stats.get('fetched')}")
        print(f"Inserted:     {run_stats.get('inserted')}")
        print(f"Duplicate:    {run_stats.get('duplicate')}")
        print(f"Filtered:     {run_stats.get('filtered')}")
        print(f"Failed:       {run_stats.get('failed')}")
        if run_stats.get("stop_reason"):
            print(f"Stop Reason:  {run_stats.get('stop_reason')}")
        if run_stats.get("error"):
            print(f"Error:        {run_stats.get('error')}")

        if not captured_response:
            print("[ERROR] No response captured. Ingestion failed.")
            sys.exit(1)

        # 5. Save Sanitized Raw JSON Response Sample
        reports_dir = Path("docs/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        raw_sample_path = reports_dir / "webz_raw_response_sample.json"

        raw_dict = captured_response.model_dump(mode="json")
        sanitized_json = json.dumps(raw_dict, indent=2, ensure_ascii=False)
        if settings.WEBZ_IO_API_KEY:
            sanitized_json = sanitized_json.replace(settings.WEBZ_IO_API_KEY, "[REDACTED_API_KEY]")
        raw_sample_path.write_text(sanitized_json, encoding="utf-8")
        print(f"\n[SAMPLE SAVED] Sanitized raw response saved to: {raw_sample_path}")

        # 6. Detailed Field Inventory Analysis
        print("\n" + "=" * 80)
        print("REAL WEBZ.IO RESPONSE FIELD INVENTORY")
        print("=" * 80)
        all_post_fields = set()
        all_thread_fields = set()
        has_summary_count = 0
        has_text_count = 0
        has_main_image_count = 0
        has_internal_images_count = 0
        has_external_images_count = 0
        has_external_links_count = 0
        has_author_count = 0

        for i, post in enumerate(captured_response.posts, 1):
            post_dict = post.model_dump(mode="json")
            all_post_fields.update(post_dict.keys())
            if post.thread:
                all_thread_fields.update(post.thread.model_dump(mode="json").keys())
            if post.summary and post.summary.strip():
                has_summary_count += 1
            if post.text and post.text.strip():
                has_text_count += 1
            if post.thread and post.thread.main_image:
                has_main_image_count += 1
            if post.internal_images:
                has_internal_images_count += 1
            if post.external_images:
                has_external_images_count += 1
            if post.external_links:
                has_external_links_count += 1
            if post.author and post.author.strip():
                has_author_count += 1

            publisher = post.thread.site_title or post.thread.site if post.thread else "unknown"
            print(f"  Post {i:02d}: [{post.language or 'unknown'}] '{post.title[:55]}...'")
            print(f"           Publisher: {publisher}")
            print(f"           Author:    {post.author or 'None'}")
            print(f"           Body Len:  {len(post.text or '')} chars | Summary Len: {len(post.summary or '')} chars")
            print(f"           Hero Img:  {bool(post.thread and post.thread.main_image)}")

        print(f"\nField Presence (out of {len(captured_response.posts)} real posts):")
        print(f"  - Full Body (text):       {has_text_count}/{len(captured_response.posts)}")
        print(f"  - Summary (summary):      {has_summary_count}/{len(captured_response.posts)}")
        print(f"  - Author (author):        {has_author_count}/{len(captured_response.posts)}")
        print(f"  - Hero Image:             {has_main_image_count}/{len(captured_response.posts)}")
        print(f"  - Internal Images:        {has_internal_images_count}/{len(captured_response.posts)}")
        print(f"  - External Images:        {has_external_images_count}/{len(captured_response.posts)}")
        print(f"  - External Links:         {has_external_links_count}/{len(captured_response.posts)}")
        print(f"  - Post Root Fields:       {sorted(list(all_post_fields))}")
        print(f"  - Thread Subfields:       {sorted(list(all_thread_fields))}")

        # 7. Post-Ingestion Database Verification
        from sqlalchemy import select, func
        from app.models.article import NewsArticle
        from app.models.source import NewsSource

        count_stmt = select(func.count(NewsArticle.id))
        total_articles = (await db.execute(count_stmt)).scalar()
        print("\n" + "=" * 80)
        print(f"POST-INGESTION DATABASE VERIFICATION: {total_articles} Articles Stored")
        print("=" * 80)

        articles_stmt = (
            select(
                NewsArticle.id,
                NewsArticle.title,
                NewsArticle.slug,
                NewsArticle.published_at,
                NewsArticle.language,
                NewsArticle.content_display_authorized,
                NewsArticle.image_url,
                func.length(func.coalesce(NewsArticle.full_text, "")).label("full_len"),
                func.length(func.coalesce(NewsArticle.description, "")).label("desc_len"),
                NewsSource.name.label("source_name"),
            )
            .join(NewsSource, NewsArticle.source_id == NewsSource.id, isouter=True)
            .order_by(NewsArticle.published_at.desc(), NewsArticle.id.desc())
        )
        persisted = (await db.execute(articles_stmt)).all()
        for art in persisted:
            auth_str = "AUTHORIZED (Full Body)" if art.content_display_authorized else "UNAUTHORIZED (Summary Only)"
            img_str = "IMAGE_PRESENT" if art.image_url else "NO_IMAGE"
            print(f"  ID {art.id:02d}: [{art.language}] {art.title[:50]}...")
            print(f"         Source: {art.source_name} | Rights: {auth_str} | Image: {img_str}")
            print(f"         Body: {art.full_len} chars | Summary: {art.desc_len} chars | Slug: {art.slug}")

        # 8. Post-Run Budget Ledger Status
        post_summary = await budget_service.get_period_summary(db=db)
        print("\n" + "=" * 80)
        print("BUDGET LEDGER STATUS")
        print("=" * 80)
        print(f"  - Monthly Spend To Date: ${post_summary.total_spent:.4f}")
        print(f"  - Remaining Allowance:   ${post_summary.remaining_allowance:.4f}")
        print(f"  - Monthly Ceiling:       ${post_summary.collection_ceiling:.4f}")
        print(f"  - Protected Reserve:     ${post_summary.protected_reserve:.4f}")
        print(f"  - Requests Left in API:  {captured_response.requests_left}")

if __name__ == "__main__":
    asyncio.run(main())
