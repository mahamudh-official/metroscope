from typing import List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.article import NewsArticle
from app.models.category import NewsCategory
from app.models.source import NewsSource


async def get_article_by_slug(
    db: AsyncSession, slug: str, status: Optional[str] = "published"
) -> Optional[NewsArticle]:
    """Retrieves an article by slug with eager loaded source and category.
    
    By default, restricts retrieval to 'published' status to prevent leaking
    draft, filtered, or unreleased articles.
    """
    stmt = (
        select(NewsArticle)
        .options(
            selectinload(NewsArticle.source),
            selectinload(NewsArticle.category),
        )
        .where(NewsArticle.slug == slug)
    )
    if status is not None:
        stmt = stmt.where(NewsArticle.status == status)

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_articles(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    category_slug: Optional[str] = None,
    category_id: Optional[int] = None,
    query: Optional[str] = None,
    status: str = "published",
    is_trending: Optional[bool] = None,
    is_breaking: Optional[bool] = None,
    cluster_id: Optional[str] = None,
) -> Tuple[List[NewsArticle], int]:
    """Retrieves paginated articles with optional category, editorial, and search filters.
    
    Returns (articles, total_count).
    """
    base_query = select(NewsArticle).where(NewsArticle.status == status)

    # Filter by category
    if category_slug:
        base_query = base_query.join(NewsArticle.category).where(
            NewsCategory.slug == category_slug.lower().strip()
        )
    elif category_id:
        base_query = base_query.where(NewsArticle.category_id == category_id)

    # Filter by editorial intelligence flags
    if is_trending is not None:
        base_query = base_query.where(NewsArticle.is_trending == is_trending)
    if is_breaking is not None:
        base_query = base_query.where(NewsArticle.is_breaking == is_breaking)
    if cluster_id:
        base_query = base_query.where(NewsArticle.cluster_id == cluster_id)

    # Filter by search keyword
    if query and query.strip():
        search_term = f"%{query.strip()}%"
        base_query = base_query.where(
            NewsArticle.title.ilike(search_term) | NewsArticle.description.ilike(search_term)
        )

    # Count total matching rows
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_stmt)
    total_count = total_result.scalar_one()

    # Paginate and sort by published_at descending
    offset = (page - 1) * page_size
    articles_stmt = (
        base_query.options(
            selectinload(NewsArticle.source),
            selectinload(NewsArticle.category),
        )
        .order_by(NewsArticle.published_at.desc(), NewsArticle.id.desc())
        .offset(offset)
        .limit(page_size)
    )

    articles_result = await db.execute(articles_stmt)
    articles = list(articles_result.scalars().all())

    return articles, total_count


async def get_related_articles(
    db: AsyncSession,
    article_id: int,
    category_id: Optional[int] = None,
    cluster_id: Optional[str] = None,
    limit: int = 4,
) -> List[NewsArticle]:
    """Retrieves related articles based on shared story cluster or category."""
    # Priority 1: Multi-source cluster match (same story from other publishers)
    if cluster_id:
        cluster_stmt = (
            select(NewsArticle)
            .options(
                selectinload(NewsArticle.source),
                selectinload(NewsArticle.category),
            )
            .where(
                NewsArticle.cluster_id == cluster_id,
                NewsArticle.id != article_id,
                NewsArticle.status == "published",
            )
            .order_by(NewsArticle.published_at.desc())
            .limit(limit)
        )
        cluster_res = await db.execute(cluster_stmt)
        related = list(cluster_res.scalars().all())
        if len(related) >= limit:
            return related
    else:
        related = []

    # Priority 2: Same category fill-in
    remaining = limit - len(related)
    if remaining > 0 and category_id:
        exclude_ids = [article_id] + [r.id for r in related]
        cat_stmt = (
            select(NewsArticle)
            .options(
                selectinload(NewsArticle.source),
                selectinload(NewsArticle.category),
            )
            .where(
                NewsArticle.category_id == category_id,
                NewsArticle.id.not_in(exclude_ids),
                NewsArticle.status == "published",
            )
            .order_by(NewsArticle.published_at.desc())
            .limit(remaining)
        )
        cat_res = await db.execute(cat_stmt)
        related.extend(list(cat_res.scalars().all()))

    return related
