import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.source import NewsSource
    from app.models.category import NewsCategory
    from app.models.social import SocialPost


class NewsArticle(Base, TimestampMixin):
    """Normalized news discovery record indexed from Webz.io News API.
    
    In compliance with publisher copyrights, stores only discovery metadata:
    title, canonical URL, source attribution, and brief summary.
    Full body scraping and republication are strictly prohibited.
    """

    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(600), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Full article body text (raw root-level Webz.io text field)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Explicit publication rights authorization flag
    content_display_authorized: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("news_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("news_categories.id", ondelete="SET NULL"),
        nullable=True,
    )

    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    # Webz.io provider UUID (unique, nullable for legacy articles)
    uuid: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=True,
    )
    author: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    # Publisher display name from thread.site_title (preferred for attribution)
    publisher_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    topics: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    # Raw provider categories (JSON list)
    webz_categories: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    trust_indicators: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    image_metadata: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Sentiment from provider
    sentiment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    country: Mapped[Optional[str]] = mapped_column(String(10), index=True, nullable=True)

    published_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    discovered_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    # When the provider crawled the article (Webz.io: post.crawled)
    crawled_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="published",
        nullable=False,
    )

    # Phase 4: Quality scoring, editorial intelligence, and clustering
    quality_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default="0.0",
        nullable=False,
    )
    is_trending: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    is_breaking: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    cluster_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        index=True,
        nullable=True,
    )
    filter_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    source: Mapped[Optional["NewsSource"]] = relationship(
        "NewsSource",
        back_populates="articles",
        lazy="selectin",
    )
    category: Mapped[Optional["NewsCategory"]] = relationship(
        "NewsCategory",
        back_populates="articles",
        lazy="selectin",
    )
    social_posts: Mapped[list["SocialPost"]] = relationship(
        "SocialPost",
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_news_articles_category_published", "category_id", "published_at"),
        Index("ix_news_articles_status_published", "status", "published_at"),
        Index("ix_news_articles_trending_published", "is_trending", "published_at"),
        Index("ix_news_articles_breaking_published", "is_breaking", "published_at"),
    )

    def __repr__(self) -> str:
        return f"<NewsArticle id={self.id} slug='{self.slug[:30]}...'>"
