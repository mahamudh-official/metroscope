"""Create social_posts table for automated social publishing

Revision ID: 0006_social_publishing
Revises: 0005_remove_redundant_indexes
Create Date: 2026-11-07 22:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic (max 32 chars for alembic_version)
revision: str = "0006_social_publishing"
down_revision: Union[str, None] = "0005_remove_redundant_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "social_posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("article_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("external_post_id", sa.String(length=128), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["news_articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "platform", name="uq_social_posts_article_platform"),
    )
    op.create_index("ix_social_posts_article_id", "social_posts", ["article_id"], unique=False)
    op.create_index("ix_social_posts_platform", "social_posts", ["platform"], unique=False)
    op.create_index("ix_social_posts_status", "social_posts", ["status"], unique=False)
    op.create_index("ix_social_posts_external_post_id", "social_posts", ["external_post_id"], unique=False)
    op.create_index("ix_social_posts_status_platform", "social_posts", ["status", "platform"], unique=False)
    op.create_index("ix_social_posts_scheduled_at", "social_posts", ["scheduled_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_social_posts_scheduled_at", table_name="social_posts")
    op.drop_index("ix_social_posts_status_platform", table_name="social_posts")
    op.drop_index("ix_social_posts_external_post_id", table_name="social_posts")
    op.drop_index("ix_social_posts_status", table_name="social_posts")
    op.drop_index("ix_social_posts_platform", table_name="social_posts")
    op.drop_index("ix_social_posts_article_id", table_name="social_posts")
    op.drop_table("social_posts")
