from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.article import NewsArticle


class NewsCategory(Base, TimestampMixin):
    """Editorial news category classification (e.g. World, US, Technology, Business)."""

    __tablename__ = "news_categories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)

    # Relationships
    articles: Mapped[List["NewsArticle"]] = relationship(
        "NewsArticle",
        back_populates="category",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<NewsCategory id={self.id} slug='{self.slug}'>"
