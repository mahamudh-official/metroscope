import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db.session import async_engine
from sqlalchemy import text

async def main():
    async with async_engine.connect() as conn:
        res = await conn.execute(text(
            "SELECT id, uuid, title, author, publisher_name, status, filter_reason, canonical_url, published_at "
            "FROM news_articles WHERE id >= 45 ORDER BY id ASC"
        ))
        rows = res.fetchall()
        print(f"Total newly inserted articles: {len(rows)}")
        for r in rows:
            print(f"ID {r[0]:02d} | Status: {r[5]} | Author: '{r[3]}' | Publisher: '{r[4][:30]}' | Reason: {r[6]}")
            print(f"      Title: {r[2]}")
            print(f"      URL:   {r[7]}")
            print("-" * 120)

        # Total counts
        counts = await conn.execute(text(
            "SELECT count(*), count(*) FILTER (WHERE status='published'), count(*) FILTER (WHERE status='filtered') FROM news_articles"
        ))
        c = counts.fetchone()
        print(f"\nDATABASE TOTALS: Total: {c[0]}, Published: {c[1]}, Filtered: {c[2]}")

    await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
