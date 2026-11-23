"""MetroScope Database Quarantine Script for Synthetic NASA Article (ID 34).

Transitions Article ID 34 from status="published" to status="filtered".
Filter reason: "Synthetic test fixture; source URL 404; hero image returns HTML".
Preserves all provenance, fields, and record history. Zero records deleted.
"""

import asyncio
import sys
sys.path.insert(0, "backend")

from app.db.session import async_session_factory
from app.models.article import NewsArticle
from sqlalchemy import select, update


TARGET_ID = 34
TARGET_UUID = "nasa-rover-2026-auth"
FILTER_REASON = "Synthetic test fixture; source URL 404; hero image returns HTML"


async def quarantine_article_34():
    async with async_session_factory() as session:
        # 1. Fetch and verify record identity
        result = await session.execute(
            select(NewsArticle).where(NewsArticle.id == TARGET_ID)
        )
        article = result.scalar_one_or_none()
        if not article:
            raise RuntimeError(f"Target article ID {TARGET_ID} not found in database.")

        if article.uuid != TARGET_UUID:
            raise RuntimeError(
                f"UUID mismatch on article {TARGET_ID}: expected '{TARGET_UUID}', found '{article.uuid}'"
            )

        print(f"Target record confirmed: ID={article.id}, UUID={article.uuid}, Title='{article.title}'")
        print(f"Pre-quarantine status: '{article.status}'")

        # 2. Update status and filter_reason
        await session.execute(
            update(NewsArticle)
            .where(NewsArticle.id == TARGET_ID)
            .values(
                status="filtered",
                filter_reason=FILTER_REASON,
            )
        )
        await session.commit()
        print("Updated Article ID 34 to status='filtered'.")

        # 3. Post-quarantine verification
        res_after = await session.execute(
            select(NewsArticle).where(NewsArticle.id == TARGET_ID)
        )
        updated_art = res_after.scalar_one()
        assert updated_art.status == "filtered", f"Expected 'filtered', got '{updated_art.status}'"
        assert updated_art.filter_reason == FILTER_REASON, "Filter reason mismatch"
        assert updated_art.uuid == TARGET_UUID, "UUID altered!"
        assert updated_art.canonical_url == "https://www.nasa.gov/news/mars-river-system-2026"

        # 4. Global database counts
        pub_res = await session.execute(select(NewsArticle).where(NewsArticle.status == "published"))
        fil_res = await session.execute(select(NewsArticle).where(NewsArticle.status == "filtered"))
        tot_res = await session.execute(select(NewsArticle))
        
        published = pub_res.scalars().all()
        filtered = fil_res.scalars().all()
        total = tot_res.scalars().all()

        print(f"\nFinal State Audit:")
        print(f"  Total records: {len(total)} (Zero hard deletions)")
        print(f"  Published records: {len(published)}")
        print(f"  Filtered records: {len(filtered)}")

        assert len(total) == 21, f"Expected 21 total records, found {len(total)}"
        assert len(published) == 0, f"Expected 0 published records, found {len(published)}"
        assert len(filtered) == 21, f"Expected 21 filtered records, found {len(filtered)}"
        print("Quarantine completed successfully. Active database has exactly 0 published and 21 filtered records.")


if __name__ == "__main__":
    asyncio.run(quarantine_article_34())
