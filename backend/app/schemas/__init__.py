"""Pydantic v2 schemas for request validation and response serialization."""

from app.schemas.health import HealthResponse
from app.schemas.pagination import PaginatedResponse
from app.schemas.source import SourceBase, SourceResponse
from app.schemas.category import CategoryBase, CategoryResponse
from app.schemas.article import ArticleBase, ArticleListItem, ArticleDetail
from app.schemas.canonical_article import CanonicalMetroScopeArticle, SCHEMA_VERSION
from app.schemas.ingestion import IngestionRunResponse

__all__ = [
    "HealthResponse",
    "PaginatedResponse",
    "SourceBase",
    "SourceResponse",
    "CategoryBase",
    "CategoryResponse",
    "ArticleBase",
    "ArticleListItem",
    "ArticleDetail",
    "CanonicalMetroScopeArticle",
    "SCHEMA_VERSION",
    "IngestionRunResponse",
]
