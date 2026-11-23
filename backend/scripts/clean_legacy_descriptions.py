import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import async_session_factory, async_engine
from app.models.article import NewsArticle
from sqlalchemy import or_, select

FABRICATED_DESCRIPTION = (
    "Comprehensive wire coverage and primary reporting. "
    "Access the original publication for full context."
)


async def main():
    async with async_session_factory() as session:
        result = await session.execute(
            select(NewsArticle).where(
                or_(
                    NewsArticle.description.like("%Discovered via GDELT%"),
                    NewsArticle.description == FABRICATED_DESCRIPTION,
                )
            )
        )
        articles = result.scalars().all()
        print(f"Found {len(articles)} legacy/boilerplate articles to clear description to NULL")
        for a in articles:
            a.description = None
        await session.commit()
        print("Successfully updated descriptions.")
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
