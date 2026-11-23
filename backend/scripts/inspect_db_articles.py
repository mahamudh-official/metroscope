import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.db.session import async_session_factory, async_engine
from app.models.article import NewsArticle
from app.models.source import NewsSource
from app.models.category import NewsCategory

async def inspect():
    async with async_session_factory() as db:
        res = await db.execute(select(NewsArticle).order_by(NewsArticle.id))
        articles = res.scalars().all()
        print(f"Total articles in DB: {len(articles)}")
        print(f"{'ID':<3} | {'Status':<9} | {'Category':<11} | {'Domain':<22} | {'Publisher':<25} | {'Author':<18} | {'Title'}")
        print("-" * 140)
        for a in articles:
            source = await db.get(NewsSource, a.source_id) if a.source_id else None
            cat = await db.get(NewsCategory, a.category_id) if a.category_id else None
            dom = (source.domain if source else '')[:22]
            pub = (a.publisher_name or '')[:25]
            auth = (a.author or 'None')[:18]
            c_slug = cat.slug if cat else 'None'
            print(f"{a.id:<3} | {a.status:<9} | {c_slug:<11} | {dom:<22} | {pub:<25} | {auth:<18} | {a.title[:45]}")
    await async_engine.dispose()

if __name__ == "__main__":
    asyncio.run(inspect())
