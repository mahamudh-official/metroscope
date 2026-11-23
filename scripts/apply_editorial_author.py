"""One-time, idempotent update: set author = 'MetroScope News Desk' on all existing articles.

Touches ONLY the `author` column. No rows are deleted; titles, content, images,
dates, status, and publisher/source data are unchanged.
"""
import asyncio
import sys

sys.path.insert(0, "backend")

from sqlalchemy import text

from app.db.session import async_engine
from app.services.normalizer_service import EDITORIAL_AUTHOR


async def main() -> None:
    async with async_engine.begin() as conn:
        before = (await conn.execute(text("SELECT count(id) FROM news_articles"))).scalar()
        res = await conn.execute(
            text(
                "UPDATE news_articles SET author = :a "
                "WHERE author IS DISTINCT FROM :a"
            ),
            {"a": EDITORIAL_AUTHOR},
        )
        total = (await conn.execute(text("SELECT count(id) FROM news_articles"))).scalar()
        correct = (
            await conn.execute(
                text("SELECT count(id) FROM news_articles WHERE author = :a"),
                {"a": EDITORIAL_AUTHOR},
            )
        ).scalar()
    print(f"rows updated: {res.rowcount}; total rows: {before}->{total}; with desk author: {correct}")


if __name__ == "__main__":
    asyncio.run(main())
