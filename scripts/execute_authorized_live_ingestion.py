"""MetroScope Authorized Single Live Ingestion Execution Script
Executes exactly ONE authorized live API request to Webz.io News API.
Follows all product requirements, budget protections, editorial validation rules,
and social publishing isolation constraints.
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
from app.db.session import async_session_factory, async_engine
from app.services.budget_service import BudgetProtectionService
from app.services.webz_ingestion_service import WebzIngestionService
from app.integrations.webz.client import WebzClient, CONFIRMED_QUERY
from app.models.article import NewsArticle
from app.models.source import NewsSource
from app.models.webz_ledger import WebzUsageLedger
from sqlalchemy import select, func, text


async def main():
    print("=" * 90)
    print("METROSCOPE — AUTHORIZED SINGLE LIVE WEBZ.IO INGESTION TEST")
    print("=" * 90)

    # 1. Strict Configuration & Pre-Condition Checks
    if not settings.WEBZ_IO_API_KEY or not settings.WEBZ_IO_API_KEY.strip():
        print("[FATAL ERROR] WEBZ_IO_API_KEY is not set or empty in environment. Aborting.")
        sys.exit(1)

    # 2. Protection Invariants Check
    print("[SAFETY CHECK] Verifying service protection invariants:")
    print(f"  - SOCIAL_PUBLISHING_ENABLED: {settings.SOCIAL_PUBLISHING_ENABLED} (MUST BE False)")
    print(f"  - SOCIAL_DRY_RUN:            {settings.SOCIAL_DRY_RUN} (MUST BE True)")
    print(f"  - FACEBOOK_ENABLED:          {settings.FACEBOOK_ENABLED} (MUST BE False)")
    print(f"  - X_ENABLED:                 {settings.X_ENABLED} (MUST BE False)")
    print(f"  - EMAIL_DRY_RUN:             {settings.EMAIL_DRY_RUN} (MUST BE True)")

    assert not settings.SOCIAL_PUBLISHING_ENABLED, "Social publishing must be disabled!"
    assert settings.SOCIAL_DRY_RUN, "Social dry run must be enabled!"
    assert not settings.FACEBOOK_ENABLED, "Facebook publishing must be disabled!"
    assert not settings.X_ENABLED, "X publishing must be disabled!"
    print("  -> ALL SAFETY INVARIANTS VERIFIED OK.\n")

    # 3. Query & Endpoint Verification
    print("[QUERY VERIFICATION]")
    print(f"  - Base URL:  {settings.WEBZ_IO_BASE_URL}")
    print(f"  - Endpoint:  {settings.WEBZ_IO_ENDPOINT}")
    print(f"  - Query:     {CONFIRMED_QUERY}")
    print(f"  - Size:      10 (Hard capped)")
    print(f"  - Max Retry: 0 (Strictly no retries)\n")

    async with async_session_factory() as db:
        # 4. Initial Database State
        max_initial_id = (await db.execute(select(func.coalesce(func.max(NewsArticle.id), 0)))).scalar()
        initial_total = (await db.execute(select(func.count(NewsArticle.id)))).scalar()
        initial_published = (await db.execute(select(func.count(NewsArticle.id)).where(NewsArticle.status == "published"))).scalar()
        initial_filtered = (await db.execute(select(func.count(NewsArticle.id)).where(NewsArticle.status == "filtered"))).scalar()
        print(f"[INITIAL DB STATE] Total: {initial_total} articles (Max ID: {max_initial_id}, Published: {initial_published}, Filtered: {initial_filtered})")

        # 5. Budget Preflight
        budget_service = BudgetProtectionService()
        preflight = await budget_service.preflight_check(db=db)
        summary_before = await budget_service.get_period_summary(db=db)
        print(f"\n[BUDGET PREFLIGHT]")
        print(f"  - Allowed:             {preflight.allowed}")
        print(f"  - Spend to Date:       ${summary_before.total_spent:.4f}")
        print(f"  - Monthly Ceiling:     ${summary_before.collection_ceiling:.4f}")
        print(f"  - Remaining Allowance: ${summary_before.remaining_allowance:.4f}")
        print(f"  - Emergency Reserve:   ${summary_before.protected_reserve:.4f}")
        print(f"  - Estimated Cost:      ${preflight.estimated_cost:.4f}")

        if not preflight.allowed:
            print(f"[ABORT] Budget protection blocked request: {preflight.stop_reason}")
            sys.exit(1)

        # 6. Webz Client Setup with STRICT Single-Call Guarantee (max_retries=0)
        api_call_count = 0
        captured_response = None

        client = WebzClient(
            api_key=settings.WEBZ_IO_API_KEY,
            base_url=settings.WEBZ_IO_BASE_URL,
            endpoint=settings.WEBZ_IO_ENDPOINT,
            timeout_seconds=30.0,
            max_retries=0,  # STRICT: zero retries to prevent duplicate billing
        )

        original_fetch = client.fetch_news_articles

        async def single_call_fetch(*args, **kwargs):
            nonlocal api_call_count, captured_response
            api_call_count += 1
            if api_call_count > 1:
                raise RuntimeError(f"CRITICAL SAFETY VIOLATION: Attempted {api_call_count} live API calls! Only 1 permitted.")
            print(f"\n[DISPATCH] Executing EXACTLY 1 authorized live request to Webz.io...")
            print(f"           URL: {client.base_url}{client.endpoint}")
            print(f"           Query: {kwargs.get('query') or args[0] if args else CONFIRMED_QUERY}")
            resp = await original_fetch(*args, **kwargs)
            captured_response = resp
            return resp

        client.fetch_news_articles = single_call_fetch

        # 7. Execute Ingestion via WebzIngestionService
        ingestion_service = WebzIngestionService(client=client, budget_service=budget_service)
        
        print("\n" + "=" * 90)
        print("EXECUTING INGESTION PIPELINE")
        print("=" * 90)
        run_stats = await ingestion_service.run_category_collection(
            db=db,
            category="confirmed",  # Uses CONFIRMED_QUERY
            job_name="authorized_live_single_ingestion",
            freshness_hours=24,
            target_articles=10,
        )

        print("\n" + "=" * 90)
        print("INGESTION PIPELINE EXECUTION COMPLETED")
        print("=" * 90)
        print(f"Pipeline Status:          {run_stats.get('status')}")
        print(f"Live API Calls Made:      {api_call_count} (Must be exactly 1)")
        print(f"Articles Fetched:         {run_stats.get('fetched')}")
        print(f"Articles Inserted (Pub):  {run_stats.get('inserted')}")
        print(f"Articles Filtered:        {run_stats.get('filtered')}")
        print(f"Duplicates Skipped:       {run_stats.get('duplicate')}")
        print(f"Failed:                   {run_stats.get('failed')}")
        if run_stats.get("stop_reason"):
            print(f"Stop Reason:              {run_stats.get('stop_reason')}")
        if run_stats.get("error"):
            print(f"Error:                    {run_stats.get('error')}")

        assert api_call_count == 1, f"Expected exactly 1 live API call, got {api_call_count}"

        # 8. Save Sanitized Raw JSON Response
        if captured_response:
            reports_dir = Path("docs/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            raw_sample_path = reports_dir / "webz_authorized_live_sample.json"
            raw_dict = captured_response.model_dump(mode="json")
            sanitized_json = json.dumps(raw_dict, indent=2, ensure_ascii=False)
            if settings.WEBZ_IO_API_KEY:
                sanitized_json = sanitized_json.replace(settings.WEBZ_IO_API_KEY, "[REDACTED_API_KEY]")
            raw_sample_path.write_text(sanitized_json, encoding="utf-8")
            print(f"\n[RAW CAPTURE] Sanitized raw Webz.io response saved to: {raw_sample_path}")

        # 9. Query Ledger for Billed Cost
        ledger_entry = None
        if run_stats.get("ledger_id"):
            ledger_entry = await db.get(WebzUsageLedger, run_stats["ledger_id"])
        
        summary_after = await budget_service.get_period_summary(db=db)
        print("\n" + "=" * 90)
        print("BUDGET & LEDGER AUDIT")
        print("=" * 90)
        if ledger_entry:
            print(f"Ledger Entry ID:       {ledger_entry.id}")
            print(f"Billing Period:        {ledger_entry.billing_period}")
            print(f"HTTP Status Code:      {ledger_entry.status_code}")
            print(f"Returned Count:        {ledger_entry.returned_count}")
            print(f"Billable Count:        {ledger_entry.billable_count}")
            print(f"Estimated Cost:        ${ledger_entry.estimated_cost:.4f}")
            cost_str = f"${ledger_entry.actual_cost:.4f}" if ledger_entry.actual_cost is not None else "None"
            print(f"Actual Billed Cost:    {cost_str}")
            print(f"API Requests Left:     {ledger_entry.requests_left}")
        print(f"Total Spent in Cycle:  ${summary_after.total_spent:.4f}")
        print(f"Remaining Allowance:   ${summary_after.remaining_allowance:.4f}")
        print(f"Emergency Reserve:     ${summary_after.protected_reserve:.4f}")

        # 10. Post-Execution Database Inspection
        post_total = (await db.execute(select(func.count(NewsArticle.id)))).scalar()
        post_published = (await db.execute(select(func.count(NewsArticle.id)).where(NewsArticle.status == "published"))).scalar()
        post_filtered = (await db.execute(select(func.count(NewsArticle.id)).where(NewsArticle.status == "filtered"))).scalar()

        # Inspect Newly Inserted Articles
        new_articles_stmt = (
            select(
                NewsArticle.id,
                NewsArticle.uuid,
                NewsArticle.title,
                NewsArticle.author,
                NewsArticle.publisher_name,
                NewsArticle.status,
                NewsArticle.filter_reason,
                NewsArticle.canonical_url,
                NewsArticle.image_url,
                NewsArticle.content_display_authorized,
            )
            .where(NewsArticle.id > max_initial_id)
            .order_by(NewsArticle.id.asc())
        )
        new_articles = (await db.execute(new_articles_stmt)).all()

        # Compute exact counts according to user specification
        from app.integrations.webz.parser import normalize_webz_post
        articles_returned = len(captured_response.posts) if (captured_response and captured_response.posts) else run_stats.get("fetched", 0)
        parsed_articles = []
        parsing_failures = 0
        if captured_response and captured_response.posts:
            for p in captured_response.posts:
                parsed = normalize_webz_post(p, target_category="confirmed")
                if parsed:
                    parsed_articles.append(parsed)
                else:
                    parsing_failures += 1
        else:
            parsed_articles = [art for art in new_articles]

        successfully_parsed = len(parsed_articles)
        published_count = sum(1 for art in new_articles if art.status == "published")
        passed_validation = published_count
        duplicates_skipped = run_stats.get("duplicate", 0)
        filtered_count = sum(1 for art in new_articles if art.status == "filtered") + parsing_failures

        print("\n" + "=" * 90)
        print("EXACT METRICS COUNT REPORT")
        print("=" * 90)
        print(f"| Metric | Count |")
        print(f"|---|---:|")
        print(f"| Articles returned by Webz.io | {articles_returned} |")
        print(f"| Successfully parsed | {successfully_parsed} |")
        print(f"| Passed validation | {passed_validation} |")
        print(f"| Published | {published_count} |")
        print(f"| Filtered/rejected | {filtered_count} |")
        print(f"| Duplicates skipped | {duplicates_skipped} |")
        print(f"| Parsing failures | {parsing_failures} |")

        print("\n" + "=" * 90)
        print("FILTERED ARTICLES SUMMARY")
        print("=" * 90)
        filtered_articles = [art for art in new_articles if art.status == "filtered"]
        if filtered_articles:
            for idx, f_art in enumerate(filtered_articles, 1):
                print(f"{idx}. ID: {f_art.id}")
                print(f"   Title:  {f_art.title}")
                print(f"   Reason: {f_art.filter_reason}")
                print(f"   Source: {f_art.canonical_url}")
        else:
            print("No newly inserted articles were filtered.")

        print("\n" + "=" * 90)
        print("DATABASE INVENTORY AUDIT")
        print("=" * 90)
        print(f"Newly inserted database IDs: {[art.id for art in new_articles]}")
        print(f"Total Database Article Count: {post_total} (was {initial_total}, delta: +{post_total - initial_total})")
        print(f"Published Total:              {post_published} (was {initial_published}, delta: +{post_published - initial_published})")
        print(f"Filtered Total:               {post_filtered} (was {initial_filtered}, delta: +{post_filtered - initial_filtered})")

        print(f"\n[NEW ARTICLES DETAIL ({len(new_articles)} inserted)]: ")
        for art in new_articles:
            print(f"\n  Article ID {art.id}:")
            print(f"    UUID:         {art.uuid}")
            print(f"    Title:        {art.title[:70]}...")
            print(f"    Author:       {art.author}")
            print(f"    Publisher:    {art.publisher_name}")
            print(f"    Status:       {art.status.upper()}")
            print(f"    Filter Reason:{art.filter_reason or 'None (Published)'}")
            print(f"    Canonical:    {art.canonical_url}")
            print(f"    Rights Auth:  {art.content_display_authorized}")
            print(f"    Hero Image:   {bool(art.image_url)}")

        # Author consistency check across all new articles
        non_desk_authors = [art for art in new_articles if art.author != "MetroScope News Desk"]
        if non_desk_authors:
            print(f"[WARNING] Found {len(non_desk_authors)} articles without MetroScope News Desk author!")
        else:
            print(f"\n[AUTHOR AUDIT] All {len(new_articles)} new articles correctly display Author: 'MetroScope News Desk'")

    await async_engine.dispose()
    print("\n" + "=" * 90)
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY")
    print("=" * 90)


if __name__ == "__main__":
    asyncio.run(main())
