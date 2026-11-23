import json
import math
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.repositories.article_repository import (
    get_article_by_slug,
    get_related_articles,
    list_articles,
)
from app.schemas.article import ArticleDetail, ArticleListItem
from app.schemas.pagination import PaginatedResponse

router = APIRouter()


@router.get(
    "/articles",
    response_model=PaginatedResponse[ArticleListItem],
    summary="List News Articles",
    description="Returns a paginated list of published news discovery records with optional category, editorial, and keyword filtering.",
)
async def get_articles(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    category: Optional[str] = Query(None, description="Category slug filter (e.g. 'technology', 'world')"),
    q: Optional[str] = Query(None, min_length=2, max_length=100, description="Search query string (min 2 chars)"),
    trending: Optional[bool] = Query(None, description="Filter by trending coverage status"),
    breaking: Optional[bool] = Query(None, description="Filter by breaking news status"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ArticleListItem]:
    articles, total_count = await list_articles(
        db,
        page=page,
        page_size=page_size,
        category_slug=category,
        query=q,
        is_trending=trending,
        is_breaking=breaking,
        status="published",
    )

    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

    items = []
    for art in articles:
        item = ArticleListItem.model_validate(art)
        if art.image_metadata:
            try:
                meta = json.loads(art.image_metadata)
                hero = meta.get("hero") or {}
                # If hero image is explicitly flagged as unauthorized, mask image_url
                if hero and not hero.get("authorized", False):
                    item.image_url = None
            except Exception:
                pass
        items.append(item)

    return PaginatedResponse[ArticleListItem](
        items=items,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/articles/{slug}",
    response_model=ArticleDetail,
    summary="Get Article Details",
    description="Retrieves a single news article record by its unique URL slug.",
)
async def get_article(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> ArticleDetail:
    article = await get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"News article with slug '{slug}' not found",
        )

    detail = ArticleDetail.model_validate(article)
    # Mask full_text if content display rights are not established
    if not getattr(article, "content_display_authorized", False):
        detail.full_text = None
        detail.content_display_authorized = False

    # Extract media metadata, captions, credits, and inline images if available
    if article.image_metadata:
        try:
            meta = json.loads(article.image_metadata)
            hero = meta.get("hero") or {}
            if hero.get("authorized", False):
                detail.image_caption = hero.get("caption")
                detail.image_credit = hero.get("credit")
            else:
                detail.image_url = None
                detail.image_caption = None
                detail.image_credit = None

            # Inline images: only return authorized inline images
            raw_inline = meta.get("inline_images") or []
            detail.inline_images = [img for img in raw_inline if img.get("authorized", False)]
        except Exception:
            pass

    return detail


@router.get(
    "/articles/{slug}/related",
    response_model=List[ArticleListItem],
    summary="Get Related Articles",
    description="Retrieves related articles sharing the same story cluster or category.",
)
async def get_article_related(
    slug: str,
    limit: int = Query(4, ge=1, le=10, description="Max related articles to return"),
    db: AsyncSession = Depends(get_db),
) -> List[ArticleListItem]:
    article = await get_article_by_slug(db, slug)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"News article with slug '{slug}' not found",
        )

    related = await get_related_articles(
        db,
        article_id=article.id,
        category_id=article.category_id,
        cluster_id=article.cluster_id,
        limit=limit,
    )

    related_items = []
    for art in related:
        item = ArticleListItem.model_validate(art)
        if art.image_metadata:
            try:
                meta = json.loads(art.image_metadata)
                hero = meta.get("hero") or {}
                if hero and not hero.get("authorized", False):
                    item.image_url = None
            except Exception:
                pass
        related_items.append(item)

    return related_items
