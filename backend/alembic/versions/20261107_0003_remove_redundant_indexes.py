"""Remove redundant standalone indexes on category_id and status

Revision ID: 0003_remove_redundant_indexes
Revises: 0002_create_news_entities
Create Date: 2026-11-07 15:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_remove_redundant_indexes"
down_revision: Union[str, None] = "0002_create_news_entities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop redundant standalone indexes that are fully covered by composite indexes:
    # 1. ix_news_articles_category_published (category_id, published_at)
    # 2. ix_news_articles_status_published (status, published_at)
    op.drop_index("ix_news_articles_category_id", table_name="news_articles")
    op.drop_index("ix_news_articles_status", table_name="news_articles")


def downgrade() -> None:
    op.create_index(
        "ix_news_articles_status",
        "news_articles",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_news_articles_category_id",
        "news_articles",
        ["category_id"],
        unique=False,
    )
