from typing import Generic, List, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic envelope for paginated list endpoints."""

    items: List[T] = Field(description="Page items")
    total: int = Field(ge=0, description="Total matching items across all pages")
    page: int = Field(ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(ge=1, le=100, description="Items per page")
    total_pages: int = Field(ge=0, description="Total number of pages available")
