"""Add extended Webz.io article fields: publisher_name, crawled_at, sentiment, webz_categories

Revision ID: 0010_webz_field_expansion
Revises: 0009_webz_io_migration
Create Date: 2026-11-11 06:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = "0010_webz_field_expansion"
down_revision: Union[str, None] = "0009_webz_io_migration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add publisher display name (from thread.site_title)
    op.add_column(
        "news_articles",
        sa.Column("publisher_name", sa.String(length=255), nullable=True),
    )
    # Add crawl timestamp (when Webz.io discovered/crawled the article)
    op.add_column(
        "news_articles",
        sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Add sentiment from provider
    op.add_column(
        "news_articles",
        sa.Column("sentiment", sa.String(length=50), nullable=True),
    )
    # Add raw provider categories (JSON list)
    op.add_column(
        "news_articles",
        sa.Column("webz_categories", sa.Text(), nullable=True),
    )

    # Update news_sources to have a longer name column if needed (safe no-op if already wider)
    # Already 255 chars, no migration needed.


def downgrade() -> None:
    op.drop_column("news_articles", "webz_categories")
    op.drop_column("news_articles", "sentiment")
    op.drop_column("news_articles", "crawled_at")
    op.drop_column("news_articles", "publisher_name")
