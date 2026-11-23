"""MetroScope Database Quarantine Script for Non-Compliant Articles.

Quarantines the 12 articles identified in the acceptance gap audit:
IDs: 1, 2, 3, 6, 7, 9, 37, 38, 39, 40, 41, 43.
Preserves ID 34 (NASA Mars Rover) as the sole published record.
Preserves existing 8 filtered records.
No records are deleted.
"""

import sys
sys.path.insert(0, "backend")

import asyncio
from app.db.session import async_session_factory
from app.models.article import NewsArticle
from sqlalchemy import select, update


TARGET_IDS = [1, 2, 3, 6, 7, 9, 37, 38, 39, 40, 41, 43]


async def quarantine():
    async with async_session_factory() as session:
        result = await session.execute(
            select(NewsArticle).where(NewsArticle.id.in_(TARGET_IDS))
        )
        articles = result.scalars().all()
        if len(articles) != 12:
            raise RuntimeError(f"Expected 12 target articles, found {len(articles)}")

        for a in articles:
            if a.status != "published":
                raise RuntimeError(
                    f"Discrepancy detected: Article {a.id} has status '{a.status}', expected 'published'. Aborting."
                )
            print(f"Verified candidate ID {a.id:2d}: {a.title[:45]} | status: {a.status}")

        # Update target records to status="filtered"
        await session.execute(
            update(NewsArticle)
            .where(NewsArticle.id.in_(TARGET_IDS))
            .values(status="filtered")
        )
        await session.commit()
        print("Updated 12 articles to status='filtered'.")

        # Verify state
        pub_res = await session.execute(select(NewsArticle).where(NewsArticle.status == "published"))
        fil_res = await session.execute(select(NewsArticle).where(NewsArticle.status == "filtered"))
        published = pub_res.scalars().all()
        filtered = fil_res.scalars().all()

        print(f"\nFinal Audit Count: {len(published)} published, {len(filtered)} filtered.")
        assert len(published) == 1, f"Expected 1 published, got {len(published)}"
        assert published[0].id == 34, f"Expected ID 34 to be published, got {published[0].id}"
        assert len(filtered) == 20, f"Expected 20 filtered, got {len(filtered)}"
        print(f"Retained Published Article: ID {published[0].id} - '{published[0].title}'")


if __name__ == "__main__":
    asyncio.run(quarantine())
