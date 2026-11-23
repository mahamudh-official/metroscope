"""MetroScope Content Audit & Inventory Script
Inspects the database and outputs comprehensive metrics across all categories,
publishers, date windows, quality scores, and content attributes.
"""
import asyncio
import datetime
import os
import sys
from collections import Counter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.article import NewsArticle
from app.models.source import NewsSource
from app.models.category import NewsCategory
from app.models.ingestion import DiscoveryIngestionRun

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://metroscope_user:metroscope_secure_password@127.0.0.1:5433/metroscope",
)

async def audit_database():
    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # 1. Total articles & sources
        total_articles = (await session.execute(select(func.count(NewsArticle.id)))).scalar() or 0
        published_articles = (await session.execute(
            select(func.count(NewsArticle.id)).where(NewsArticle.status == "published")
        )).scalar() or 0
        filtered_articles = (await session.execute(
            select(func.count(NewsArticle.id)).where(NewsArticle.status != "published")
        )).scalar() or 0
        total_sources = (await session.execute(select(func.count(NewsSource.id)))).scalar() or 0
        active_sources = (await session.execute(
            select(func.count(NewsSource.id)).where(NewsSource.is_active.is_(True))
        )).scalar() or 0

        # 2. Articles by category (all approved categories)
        cat_stmt = (
            select(NewsCategory.slug, NewsCategory.name, func.count(NewsArticle.id))
            .join(NewsArticle, NewsArticle.category_id == NewsCategory.id, isouter=True)
            .group_by(NewsCategory.id, NewsCategory.slug, NewsCategory.name)
            .order_by(func.count(NewsArticle.id).desc())
        )
        cat_rows = (await session.execute(cat_stmt)).all()

        # 3. Articles by top publishers
        pub_stmt = (
            select(NewsSource.domain, NewsSource.name, func.count(NewsArticle.id))
            .join(NewsArticle, NewsArticle.source_id == NewsSource.id)
            .group_by(NewsSource.id, NewsSource.domain, NewsSource.name)
            .order_by(func.count(NewsArticle.id).desc())
            .limit(15)
        )
        pub_rows = (await session.execute(pub_stmt)).all()

        # 4. Articles by timeframe
        now = datetime.datetime.now(datetime.timezone.utc)
        h24 = now - datetime.timedelta(hours=24)
        d7 = now - datetime.timedelta(days=7)
        d30 = now - datetime.timedelta(days=30)

        art_24h = (await session.execute(
            select(func.count(NewsArticle.id)).where(NewsArticle.published_at >= h24)
        )).scalar() or 0
        art_7d = (await session.execute(
            select(func.count(NewsArticle.id)).where(NewsArticle.published_at >= d7)
        )).scalar() or 0
        art_30d = (await session.execute(
            select(func.count(NewsArticle.id)).where(NewsArticle.published_at >= d30)
        )).scalar() or 0

        # 5. Missing attributes
        missing_summary = (await session.execute(
            select(func.count(NewsArticle.id)).where(
                (NewsArticle.description.is_(None)) | (NewsArticle.description == "")
            )
        )).scalar() or 0
        missing_image = (await session.execute(
            select(func.count(NewsArticle.id)).where(
                (NewsArticle.image_url.is_(None)) | (NewsArticle.image_url == "")
            )
        )).scalar() or 0

        # 6. Quality & duplicates
        low_quality = (await session.execute(
            select(func.count(NewsArticle.id)).where(NewsArticle.quality_score < 60.0)
        )).scalar() or 0
        high_quality = (await session.execute(
            select(func.count(NewsArticle.id)).where(NewsArticle.quality_score >= 70.0)
        )).scalar() or 0

        # 7. Ingestion runs
        ingest_runs = (await session.execute(select(func.count(DiscoveryIngestionRun.id)))).scalar() or 0

        print("=" * 70)
        print("METROSCOPE CONTENT INVENTORY AUDIT")
        print("=" * 70)
        print(f"Total Ingested Articles     : {total_articles}")
        print(f"  - Status = 'published'    : {published_articles}")
        print(f"  - Status != 'published'   : {filtered_articles}")
        print(f"Total News Sources          : {total_sources} (Active: {active_sources})")
        print(f"Total Ingestion Runs        : {ingest_runs}")
        print("-" * 70)
        print(f"Publication Freshness:")
        print(f"  - Last 24 Hours           : {art_24h}")
        print(f"  - Last 7 Days             : {art_7d}")
        print(f"  - Last 30 Days            : {art_30d}")
        print(f"  - Older than 30 Days      : {total_articles - art_30d}")
        print("-" * 70)
        print(f"Content Completeness & Quality:")
        print(f"  - Missing Summary         : {missing_summary} ({(missing_summary/max(total_articles,1)*100):.1f}%)")
        print(f"  - Missing Image           : {missing_image} ({(missing_image/max(total_articles,1)*100):.1f}%)")
        print(f"  - Quality < 60.0          : {low_quality}")
        print(f"  - Quality >= 70.0 (High)  : {high_quality}")
        print("-" * 70)
        print("Category Distribution:")
        zero_categories = []
        for slug, name, count in cat_rows:
            pct = (count / max(total_articles, 1)) * 100
            print(f"  * {slug:15} ({name}): {count:3} articles ({pct:5.1f}%)")
            if count == 0:
                zero_categories.append(slug)
        print("-" * 70)
        print(f"Categories with 0 articles: {', '.join(zero_categories) if zero_categories else 'None'}")
        print("-" * 70)
        print("Top Publishers:")
        for domain, name, count in pub_rows:
            print(f"  * {domain:35} : {count:3} articles")
        print("=" * 70)

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(audit_database())
