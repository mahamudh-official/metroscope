"""Remove redundant single-column indexes on is_trending and is_breaking

Revision ID: 0005_remove_redundant_indexes
Revises: 0004_quality_editorial_seo
Create Date: 2026-11-07 20:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic (max 32 chars for alembic_version)
revision: str = "0005_remove_redundant_indexes"
down_revision: Union[str, None] = "0004_quality_editorial_seo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop single-column indexes rendered redundant by existing composite indexes:
    # - ix_news_articles_trending_published (is_trending, published_at)
    # - ix_news_articles_breaking_published (is_breaking, published_at)
    op.drop_index("ix_news_articles_is_trending", table_name="news_articles")
    op.drop_index("ix_news_articles_is_breaking", table_name="news_articles")


def downgrade() -> None:
    # Re-create single-column indexes if downgraded
    op.create_index("ix_news_articles_is_trending", "news_articles", ["is_trending"], unique=False)
    op.create_index("ix_news_articles_is_breaking", "news_articles", ["is_breaking"], unique=False)
