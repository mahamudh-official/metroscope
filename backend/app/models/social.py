import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.article import NewsArticle


class SocialPost(Base, TimestampMixin):
    """Tracks automated social media publication attempts and platform post IDs."""

    __tablename__ = "social_posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("news_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(
        String(20),  # "facebook", "x"
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),  # "PENDING", "PROCESSING", "PUBLISHED", "PARTIALLY_PUBLISHED", "FAILED", "RETRYABLE", "CANCELLED", "FAILED_AMBIGUOUS", "RECONCILIATION_REQUIRED"
        default="PENDING",
        nullable=False,
        index=True,
    )
    post_type: Mapped[Optional[str]] = mapped_column(
        String(20),  # "photo", "text"
        nullable=True,
        default="photo",
    )
    external_post_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    external_photo_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    external_comment_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    comment_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    extra_metadata: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    scheduled_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    published_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    recovered_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    recovery_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationship back to NewsArticle
    article: Mapped["NewsArticle"] = relationship(
        "NewsArticle",
        back_populates="social_posts",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("article_id", "platform", name="uq_social_posts_article_platform"),
        Index("ix_social_posts_status_platform", "status", "platform"),
        Index("ix_social_posts_scheduled_at", "scheduled_at"),
        Index("ix_social_posts_status_updated_at", "status", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<SocialPost id={self.id} article_id={self.article_id} platform='{self.platform}' status='{self.status}'>"
