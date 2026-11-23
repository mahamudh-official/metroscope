"""Create news sources, categories, articles, and ingestion runs

Revision ID: 0002_create_news_entities
Revises: 0001_initial_baseline
Create Date: 2026-11-07 14:00:00.000000

"""
from typing import Sequence, Union
import datetime
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_create_news_entities"
down_revision: Union[str, None] = "0001_initial_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INITIAL_CATEGORIES = [
    ("World", "world", "Global events, international relations, and diplomatic affairs"),
    ("US", "us", "Domestic American reporting, state policies, and national affairs"),
    ("Politics", "politics", "Elections, governance, legislation, and political analysis"),
    ("Business", "business", "Corporate updates, macroeconomics, finance, and trade"),
    ("Technology", "technology", "Artificial intelligence, computing, software, and cybersecurity"),
    ("Science", "science", "Space exploration, scientific breakthroughs, and academic research"),
    ("Health", "health", "Medicine, public health policy, and healthcare innovations"),
    ("Environment", "environment", "Climate science, renewable energy, and ecological developments"),
    ("Sports", "sports", "Major league athletics, championships, and athletic reporting"),
    ("Entertainment", "entertainment", "Film, arts, culture, media, and digital creators"),
]


def upgrade() -> None:
    # 1. Create news_sources table
    op.create_table(
        "news_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("website_url", sa.String(length=1024), nullable=True),
        sa.Column("country", sa.String(length=10), server_default="US", nullable=False),
        sa.Column("language", sa.String(length=10), server_default="en", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_sources_domain", "news_sources", ["domain"], unique=True)
    op.create_index("ix_news_sources_country", "news_sources", ["country"], unique=False)
    op.create_index("ix_news_sources_is_active", "news_sources", ["is_active"], unique=False)

    # 2. Create news_categories table
    categories_table = op.create_table(
        "news_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_news_categories_slug", "news_categories", ["slug"], unique=True)
    op.create_index("ix_news_categories_is_active", "news_categories", ["is_active"], unique=False)

    # 3. Create news_articles table
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("slug", sa.String(length=600), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("original_url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("canonical_url_hash", sa.String(length=64), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=10), server_default="en", nullable=False),
        sa.Column("country", sa.String(length=10), server_default="US", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="published", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["news_sources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["news_categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_articles_title", "news_articles", ["title"], unique=False)
    op.create_index("ix_news_articles_slug", "news_articles", ["slug"], unique=True)
    op.create_index("ix_news_articles_canonical_url_hash", "news_articles", ["canonical_url_hash"], unique=True)
    op.create_index("ix_news_articles_source_id", "news_articles", ["source_id"], unique=False)
    op.create_index("ix_news_articles_category_id", "news_articles", ["category_id"], unique=False)
    op.create_index("ix_news_articles_country", "news_articles", ["country"], unique=False)
    op.create_index("ix_news_articles_published_at", "news_articles", ["published_at"], unique=False)
    op.create_index("ix_news_articles_discovered_at", "news_articles", ["discovered_at"], unique=False)
    op.create_index("ix_news_articles_status", "news_articles", ["status"], unique=False)
    op.create_index("ix_news_articles_category_published", "news_articles", ["category_id", "published_at"], unique=False)
    op.create_index("ix_news_articles_status_published", "news_articles", ["status", "published_at"], unique=False)

    # 4. Create discovery_ingestion_runs table
    op.create_table(
        "discovery_ingestion_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=50), server_default="gdelt", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="running", nullable=False),
        sa.Column("fetched_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inserted_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicate_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_ingestion_runs_provider", "discovery_ingestion_runs", ["provider"], unique=False)
    op.create_index("ix_discovery_ingestion_runs_status", "discovery_ingestion_runs", ["status"], unique=False)

    # 5. Seed initial standard categories
    now = datetime.datetime.now(datetime.timezone.utc)
    seed_data = [
        {
            "name": name,
            "slug": slug,
            "description": desc,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        for name, slug, desc in INITIAL_CATEGORIES
    ]
    op.bulk_insert(categories_table, seed_data)


def downgrade() -> None:
    op.drop_table("discovery_ingestion_runs")
    op.drop_table("news_articles")
    op.drop_table("news_categories")
    op.drop_table("news_sources")
