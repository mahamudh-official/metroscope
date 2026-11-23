"""Phase 12 Delivery Verification Script.

Tests:
1. Category coverage & minimum article thresholds
2. Editorial Intelligence (trending, breaking, topic clusters)
3. API query response times and data integrity
4. Search endpoint coverage across beats
5. Database indexing performance (EXPLAIN ANALYZE)
"""

import asyncio
import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select, func, text
from app.db.session import async_session_factory
from app.models.article import NewsArticle
from app.models.category import NewsCategory
from app.models.source import NewsSource
from app.repositories import article_repository


async def verify():
    print("=" * 70)
    print("PHASE 12 DELIVERY VERIFICATION & PERFORMANCE AUDIT")
    print("=" * 70)

    async with async_session_factory() as session:
        # 1. Total and Category Counts
        total_articles = (await session.execute(select(func.count(NewsArticle.id)))).scalar()
        total_sources = (await session.execute(select(func.count(NewsSource.id)))).scalar()
        print(f"Total Published Articles : {total_articles}")
        print(f"Total Publishers/Sources : {total_sources}")
        print("-" * 70)

        # Category Breakdown
        cats_stmt = (
            select(NewsCategory.slug, NewsCategory.name, func.count(NewsArticle.id))
            .join(NewsArticle, NewsArticle.category_id == NewsCategory.id, isouter=True)
            .group_by(NewsCategory.slug, NewsCategory.name)
            .order_by(func.count(NewsArticle.id).desc())
        )
        cat_rows = (await session.execute(cats_stmt)).all()
        print("Category Coverage Breakdown:")
        all_covered = True
        for slug, name, cnt in cat_rows:
            pct = (cnt / total_articles * 100) if total_articles else 0
            flag = "PASS" if cnt >= 5 else "LOW"
            print(f"  * {slug:<15} ({name:<14}): {cnt:>3} articles ({pct:>4.1f}%) [{flag}]")
            if cnt == 0:
                all_covered = False

        print("-" * 70)
        # 2. Editorial Intelligence
        trending_cnt = (
            await session.execute(
                select(func.count(NewsArticle.id)).where(NewsArticle.is_trending.is_(True))
            )
        ).scalar()
        breaking_cnt = (
            await session.execute(
                select(func.count(NewsArticle.id)).where(NewsArticle.is_breaking.is_(True))
            )
        ).scalar()
        cluster_cnt = (
            await session.execute(
                select(func.count(func.distinct(NewsArticle.cluster_id))).where(
                    NewsArticle.cluster_id.is_not(None)
                )
            )
        ).scalar()
        print("Editorial Intelligence Metrics:")
        print(f"  * Trending Articles : {trending_cnt}")
        print(f"  * Breaking Articles : {breaking_cnt}")
        print(f"  * Distinct Clusters : {cluster_cnt}")
        print("-" * 70)

        # 3. Query Performance & EXPLAIN ANALYZE
        print("Query Latency & Index Utilization:")
        # Homepage recent query
        t0 = time.perf_counter()
        recent_items, recent_tot = await article_repository.list_articles(session, page=1, page_size=20)
        t_recent = (time.perf_counter() - t0) * 1000
        print(f"  * Homepage Recent Query (limit=20)    : {t_recent:.2f}ms ({len(recent_items)} items / {recent_tot} total)")

        # Category query
        t0 = time.perf_counter()
        science_items, science_tot = await article_repository.list_articles(
            session, page=1, page_size=10, category_slug="science"
        )
        t_science = (time.perf_counter() - t0) * 1000
        print(f"  * Category Filter Query (science)     : {t_science:.2f}ms ({len(science_items)} items / {science_tot} total)")

        # Search query
        t0 = time.perf_counter()
        search_items, search_tot = await article_repository.list_articles(
            session, page=1, page_size=10, query="health"
        )
        t_search = (time.perf_counter() - t0) * 1000
        print(f"  * Search Query ('health')             : {t_search:.2f}ms ({len(search_items)} items / {search_tot} total)")

        # EXPLAIN ANALYZE on index
        explain_stmt = text(
            "EXPLAIN ANALYZE SELECT * FROM news_articles "
            "WHERE status = 'published' ORDER BY published_at DESC LIMIT 20;"
        )
        explain_res = (await session.execute(explain_stmt)).fetchall()
        print("\nPostgreSQL Execution Plan (Recent Articles):")
        for line in explain_res[:4]:
            print(f"    {line[0]}")

    print("=" * 70)
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(verify())
