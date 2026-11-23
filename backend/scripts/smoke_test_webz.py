import asyncio
import datetime
import os
import sys

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.core.logging import logger
from app.db.session import async_session_factory, async_engine
from app.services.budget_service import BudgetProtectionService
from app.services.webz_ingestion_service import WebzIngestionService


async def main():
    print("=" * 70)
    print("      METROSCOPE — WEBZ.IO SINGLE PROVIDER LIVE SMOKE TEST      ")
    print("=" * 70)
    print(f"Timestamp: {datetime.datetime.now(datetime.timezone.utc).isoformat()}")
    print(f"Endpoint:  {settings.WEBZ_IO_BASE_URL}{settings.WEBZ_IO_ENDPOINT}")
    print(f"Category:  Sports (Morning Schedule Beat)")
    print(f"Ceiling:   ${settings.WEBZ_IO_COLLECTION_CEILING} (Emergency Reserve: ${settings.WEBZ_IO_PROTECTED_RESERVE})")

    if not settings.WEBZ_IO_API_KEY or not settings.WEBZ_IO_API_KEY.strip():
        print("\n[BLOCKED] WEBZ_IO_API_KEY is not configured in environment or .env file.")
        print("Owner action required: please set WEBZ_IO_API_KEY=<your_token> in .env to enable live testing.")
        return

    if "--confirm-cost" not in sys.argv:
        print("\n[AUTHORIZATION REQUIRED]")
        print("Live API calls consume provider account credits.")
        print("To authorize spending credits for a smoke test run:")
        print("  python backend/scripts/smoke_test_webz.py --confirm-cost")
        return

    print("\n[PREFLIGHT] Performing budget preflight check...")
    async with async_session_factory() as session:
        budget_service = BudgetProtectionService()
        preflight = await budget_service.preflight_check(session)
        print(f"  Allowed:             {preflight.allowed}")
        print(f"  Remaining Allowance: ${preflight.remaining_allowance}")
        print(f"  Estimated Cost:      ${preflight.estimated_cost}")

        if not preflight.allowed:
            print(f"\n[ABORTED] Budget preflight rejected: {preflight.stop_reason}")
            return

        print("\n[DISPATCH] Executing controlled single live collection request...")
        service = WebzIngestionService()
        result = await service.run_category_collection(
            db=session,
            category="sports",
            job_name="manual_smoke_test",
            freshness_hours=24,
            target_articles=settings.WEBZ_IO_TARGET_ARTICLES_PER_JOB,
        )

        print("\n" + "=" * 70)
        print("                      SMOKE TEST RESULTS                        ")
        print("=" * 70)
        print(f"Status:       {result.get('status')}")
        print(f"Fetched:      {result.get('fetched')}")
        print(f"Inserted:     {result.get('inserted')}")
        print(f"Duplicate:    {result.get('duplicate')}")
        print(f"Failed:       {result.get('failed')}")
        print(f"Stop Reason:  {result.get('stop_reason')}")
        print(f"Ledger ID:    {result.get('ledger_id')}")
        print(f"Run ID:       {result.get('run_id')}")

        summary = await budget_service.get_period_summary(session)
        print("\n--- Current Period Budget Status ---")
        print(f"Billing Period:      {summary.billing_period}")
        print(f"Total Requests:      {summary.total_requests}")
        print(f"Successful Requests: {summary.successful_requests}")
        print(f"Total Spent:         ${summary.total_spent}")
        print(f"Remaining Allowance: ${summary.remaining_allowance}")
        print(f"Emergency Reserve:   ${summary.protected_reserve} (PROTECTED)")

    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
