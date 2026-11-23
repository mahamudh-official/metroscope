"""Phase 12 Targeted Category Enrichment Pass (Tech, Business, Politics).
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import async_session_factory
from app.services.ingestion_service import IngestionService


async def main():
    target_cats = ["technology", "business", "politics"]
    print(f"Executing targeted enrichment for: {target_cats} with 15s delay...")
    async with async_session_factory() as session:
        service = IngestionService()
        results = await service.run_comprehensive_discovery(
            db=session,
            categories=target_cats,
            records_per_category=20,
            delay_between_requests=15.0,
            timespan="48h",
        )
    print("TARGETED PASS COMPLETE:", results)


if __name__ == "__main__":
    asyncio.run(main())
