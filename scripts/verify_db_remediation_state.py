import asyncio
import sys
sys.path.insert(0, "backend")

from sqlalchemy import text
from app.db.session import async_engine

async def main():
    async with async_engine.connect() as conn:
        total = (await conn.execute(text("SELECT count(id) FROM news_articles"))).scalar()
        published = (await conn.execute(text("SELECT count(id) FROM news_articles WHERE status = 'published'"))).scalar()
        filtered = (await conn.execute(text("SELECT count(id) FROM news_articles WHERE status = 'filtered'"))).scalar()
        art34 = (await conn.execute(text("SELECT id, uuid, title, status, filter_reason, canonical_url FROM news_articles WHERE id = 34"))).fetchone()
        
        print(f"DATABASE SUMMARY:")
        print(f"Total articles: {total}")
        print(f"Published articles: {published}")
        print(f"Filtered articles: {filtered}")
        print(f"Article 34: id={art34[0]}, uuid={art34[1]}, status={art34[3]}")
        print(f"Filter reason: {art34[4]}")
        print(f"Canonical URL: {art34[5]}")

if __name__ == "__main__":
    asyncio.run(main())
