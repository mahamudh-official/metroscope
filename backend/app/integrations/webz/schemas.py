import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator


class WebzThread(BaseModel):
    """Publisher and thread metadata nested inside Webz.io post."""
    model_config = ConfigDict(extra="ignore")

    uuid: Optional[str] = None
    url: Optional[str] = None
    site_full: Optional[str] = None
    site: Optional[str] = None
    site_section: Optional[str] = None
    site_categories: List[str] = Field(default_factory=list)
    section_title: Optional[str] = None
    title: Optional[str] = None
    published: Optional[str] = None
    site_type: Optional[str] = None
    country: Optional[str] = None
    main_image: Optional[str] = None
    domain_rank: Optional[int] = None
    spam_score: Optional[float] = None
    performance_score: Optional[int] = None
    # Publisher display name (preferred for attribution)
    site_title: Optional[str] = None
    # Licensing & social metadata
    licensing_agency: Optional[Any] = None
    social: Optional[Dict[str, Any]] = None

    @field_validator("site_categories", mode="before")
    @classmethod
    def coerce_site_categories(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(item) for item in v if item is not None]
        return [str(v)]


class WebzPost(BaseModel):
    """Raw Webz.io News API post record."""
    model_config = ConfigDict(extra="ignore")

    uuid: str
    url: str
    published: str
    title: str
    text: Optional[str] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    language: Optional[str] = "english"
    thread: Optional[WebzThread] = None
    entities: Optional[Dict[str, Any]] = None
    # Additional Webz.io fields
    crawled: Optional[str] = None
    updated: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    sentiment: Optional[str] = None
    breaking: Optional[bool] = False
    rating: Optional[float] = None
    ai_allow: Optional[bool] = None
    has_canonical: Optional[bool] = None
    external_links: List[str] = Field(default_factory=list)
    external_images: List[Union[Dict[str, Any], str]] = Field(default_factory=list)
    internal_images: List[Union[Dict[str, Any], str]] = Field(default_factory=list)
    syndication: Optional[Dict[str, Any]] = None
    trust: Optional[Dict[str, Any]] = None

    @field_validator("categories", "topics", "external_links", mode="before")
    @classmethod
    def coerce_string_lists(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(item) for item in v if item is not None]
        return [str(v)]

    @field_validator("external_images", "internal_images", mode="before")
    @classmethod
    def coerce_image_lists(cls, v: Any) -> List[Union[Dict[str, Any], str]]:
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return [v]


class WebzResponse(BaseModel):
    """Top-level Webz.io News API response payload."""
    model_config = ConfigDict(extra="ignore")

    posts: List[WebzPost] = Field(default_factory=list)
    total_results: Optional[int] = None
    more_results_available: Optional[int] = None
    next: Optional[str] = None
    requests_left: Optional[int] = None
    cost: Optional[Decimal] = None
    credits_used: Optional[Decimal] = None

    @field_validator("posts", mode="before")
    @classmethod
    def coerce_posts(cls, v: Any) -> List[Any]:
        if v is None:
            return []
        return v


class NormalizedWebzArticle(BaseModel):
    """Validated, normalized, metadata-only article record.
    
    Adheres strictly to Copyright safeguards: does NOT contain full text unless authorized.
    Stores discovery metadata, clean short summary, root-level text, media metadata, and rights.
    """
    uuid: str
    title: str
    summary: Optional[str] = None
    # Root-level Webz.io article text (preserved with paragraph boundaries and original language)
    full_text: Optional[str] = None
    # Publication rights authorization flags
    content_display_authorized: bool = False
    hero_image_authorized: bool = False
    inline_images_authorized: bool = False
    original_url: str
    canonical_url: str
    canonical_url_hash: str
    domain: str
    # Publisher display name from thread.site_title or fallback
    publisher_name: Optional[str] = None
    author: Optional[str] = None
    image_url: Optional[str] = None
    image_caption: Optional[str] = None
    image_credit: Optional[str] = None
    inline_images: List[Dict[str, Any]] = Field(default_factory=list)
    language: str = "en"
    country: Optional[str] = None
    published_at: datetime.datetime
    crawled_at: Optional[datetime.datetime] = None
    # Classified category slug (from classifier, not raw provider value)
    category_slug: str
    # Classification confidence score
    classification_confidence: int = 0
    # Raw provider categories from post.categories
    webz_categories: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    trust_indicators: Dict[str, Any] = Field(default_factory=dict)
    image_metadata: Dict[str, Any] = Field(default_factory=dict)
    # Sentiment from provider
    sentiment: Optional[str] = None
    # Breaking flag from provider
    is_breaking: bool = False
