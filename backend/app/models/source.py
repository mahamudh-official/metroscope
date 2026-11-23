from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.article import NewsArticle


class NewsSource(Base, TimestampMixin):
    """Represents an external publishing source or news outlet indexed by MetroScope."""

    __tablename__ = "news_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    website_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(10), index=True, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)

    # Relationships
    articles: Mapped[List["NewsArticle"]] = relationship(
        "NewsArticle",
        back_populates="source",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<NewsSource id={self.id} domain='{self.domain}'>"
