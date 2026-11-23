from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.category import NewsCategory
from app.models.article import NewsArticle


async def get_category_by_slug(
    db: AsyncSession, slug: str
) -> Optional[NewsCategory]:
    """Retrieves an active category by its unique slug."""
    stmt = select(NewsCategory).where(
        NewsCategory.slug == slug,
        NewsCategory.is_active.is_(True),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_category_by_id(
    db: AsyncSession, category_id: int
) -> Optional[NewsCategory]:
    """Retrieves an active category by ID."""
    stmt = select(NewsCategory).where(
        NewsCategory.id == category_id,
        NewsCategory.is_active.is_(True),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_categories_with_counts(
    db: AsyncSession, active_only: bool = True
) -> List[tuple[NewsCategory, int]]:
    """Returns active categories along with their published article counts."""
    # Outer join articles to count published articles
    stmt = (
        select(
            NewsCategory,
            func.count(NewsArticle.id).label("article_count"),
        )
        .outerjoin(
            NewsArticle,
            (NewsArticle.category_id == NewsCategory.id) & (NewsArticle.status == "published"),
        )
        .group_by(NewsCategory.id)
        .order_by(NewsCategory.name.asc())
    )
    if active_only:
        stmt = stmt.where(NewsCategory.is_active.is_(True))

    result = await db.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def get_all_categories_map(
    db: AsyncSession,
) -> dict[str, NewsCategory]:
    """Returns a lookup dictionary of slug -> NewsCategory for rapid classification matching."""
    stmt = select(NewsCategory).where(NewsCategory.is_active.is_(True))
    result = await db.execute(stmt)
    return {cat.slug: cat for cat in result.scalars().all()}
