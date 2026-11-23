import math
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.repositories.article_repository import list_articles
from app.repositories.category_repository import (
    get_category_by_slug,
    list_categories_with_counts,
)
from app.schemas.article import ArticleListItem
from app.schemas.category import CategoryResponse
from app.schemas.pagination import PaginatedResponse

router = APIRouter()


@router.get(
    "/categories",
    response_model=List[CategoryResponse],
    summary="List Editorial Categories",
    description="Returns all active news categories along with their published article counts.",
)
async def get_categories(
    db: AsyncSession = Depends(get_db),
) -> List[CategoryResponse]:
    categories_with_counts = await list_categories_with_counts(db, active_only=True)

    result = []
    for cat, count in categories_with_counts:
        cat_resp = CategoryResponse(
            id=cat.id,
            name=cat.name,
            slug=cat.slug,
            description=cat.description,
            is_active=cat.is_active,
            created_at=cat.created_at,
            updated_at=cat.updated_at,
            article_count=count,
        )
        result.append(cat_resp)

    return result


@router.get(
    "/categories/{slug}/articles",
    response_model=PaginatedResponse[ArticleListItem],
    summary="List Category Articles",
    description="Returns paginated articles published under a specific category slug.",
)
async def get_category_articles(
    slug: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ArticleListItem]:
    category = await get_category_by_slug(db, slug)
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"News category with slug '{slug}' not found",
        )

    articles, total_count = await list_articles(
        db,
        page=page,
        page_size=page_size,
        category_slug=slug,
        status="published",
    )

    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

    return PaginatedResponse[ArticleListItem](
        items=[ArticleListItem.model_validate(art) for art in articles],
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
