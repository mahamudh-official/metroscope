import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.source import SourceResponse
from app.schemas.category import CategoryResponse
from app.services.normalizer_service import EDITORIAL_AUTHOR


class ArticleBase(BaseModel):
    title: str = Field(max_length=512)
    slug: str = Field(max_length=600)
    description: Optional[str] = None
    original_url: str
    canonical_url: str
    image_url: Optional[str] = None
    language: str = "en"
    country: Optional[str] = None
    published_at: datetime.datetime
    status: str = "published"


class ArticleListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    description: Optional[str] = None
    canonical_url: str
    image_url: Optional[str] = None
    author: Optional[str] = None
    publisher_name: Optional[str] = None
    language: str
    country: Optional[str] = None
    published_at: datetime.datetime
    is_trending: bool = False
    is_breaking: bool = False
    source: Optional[SourceResponse] = None
    category: Optional[CategoryResponse] = None

    @model_validator(mode="after")
    def enforce_editorial_author(self) -> "ArticleListItem":
        """Public API always exposes MetroScope News Desk as author (covers legacy rows)."""
        self.author = EDITORIAL_AUTHOR
        return self
class ArticleDetail(ArticleListItem):
    model_config = ConfigDict(from_attributes=True)

    full_text: Optional[str] = None
    content_display_authorized: bool = False
    updated_at: Optional[datetime.datetime] = None
    image_caption: Optional[str] = None
    image_credit: Optional[str] = None
    inline_images: List[Dict[str, Any]] = Field(default_factory=list)
