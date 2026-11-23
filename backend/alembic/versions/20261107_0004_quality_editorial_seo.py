"""Add news quality, editorial intelligence, and clustering fields

Revision ID: 0004_quality_editorial_seo
Revises: 0003_remove_redundant_indexes
Create Date: 2026-11-07 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_quality_editorial_seo"
down_revision: Union[str, None] = "0003_remove_redundant_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add fields to news_articles
    op.add_column(
        "news_articles",
        sa.Column("quality_score", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "news_articles",
        sa.Column("is_trending", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "news_articles",
        sa.Column("is_breaking", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "news_articles",
        sa.Column("cluster_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "news_articles",
        sa.Column("filter_reason", sa.String(length=255), nullable=True),
    )

    # Indexes on news_articles
    op.create_index("ix_news_articles_is_trending", "news_articles", ["is_trending"], unique=False)
    op.create_index("ix_news_articles_is_breaking", "news_articles", ["is_breaking"], unique=False)
    op.create_index("ix_news_articles_cluster_id", "news_articles", ["cluster_id"], unique=False)
    op.create_index(
        "ix_news_articles_trending_published",
        "news_articles",
        ["is_trending", "published_at"],
        unique=False,
    )
    op.create_index(
        "ix_news_articles_breaking_published",
        "news_articles",
        ["is_breaking", "published_at"],
        unique=False,
    )

    # 2. Add filtered_count to discovery_ingestion_runs
    op.add_column(
        "discovery_ingestion_runs",
        sa.Column("filtered_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    # Drop discovery_ingestion_runs column
    op.drop_column("discovery_ingestion_runs", "filtered_count")

    # Drop indexes
    op.drop_index("ix_news_articles_breaking_published", table_name="news_articles")
    op.drop_index("ix_news_articles_trending_published", table_name="news_articles")
    op.drop_index("ix_news_articles_cluster_id", table_name="news_articles")
    op.drop_index("ix_news_articles_is_breaking", table_name="news_articles")
    op.drop_index("ix_news_articles_is_trending", table_name="news_articles")

    # Drop news_articles columns
    op.drop_column("news_articles", "filter_reason")
    op.drop_column("news_articles", "cluster_id")
    op.drop_column("news_articles", "is_breaking")
    op.drop_column("news_articles", "is_trending")
    op.drop_column("news_articles", "quality_score")
