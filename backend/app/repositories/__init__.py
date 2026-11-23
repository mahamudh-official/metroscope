"""Data access repositories."""

from app.repositories.source_repository import get_source_by_domain, get_or_create_source
from app.repositories.category_repository import (
    get_category_by_slug,
    get_category_by_id,
    list_categories_with_counts,
    get_all_categories_map,
)
from app.repositories.article_repository import get_article_by_slug, list_articles
from app.repositories.ingestion_repository import (
    create_ingestion_run,
    update_ingestion_run,
)

__all__ = [
    "get_source_by_domain",
    "get_or_create_source",
    "get_category_by_slug",
    "get_category_by_id",
    "list_categories_with_counts",
    "get_all_categories_map",
    "get_article_by_slug",
    "list_articles",
    "create_ingestion_run",
    "update_ingestion_run",
]
