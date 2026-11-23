"""Add recovery fields and expand status length for stale social posts

Revision ID: 0007_stale_recovery
Revises: 0006_social_publishing
Create Date: 2026-11-07 23:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic (max 32 chars for alembic_version)
revision: str = "0007_stale_recovery"
down_revision: Union[str, None] = "0006_social_publishing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Expand status column to VARCHAR(32) to support RECONCILIATION_REQUIRED / FAILED_AMBIGUOUS
    op.alter_column(
        "social_posts",
        "status",
        existing_type=sa.String(length=20),
        type_=sa.String(length=32),
        existing_nullable=False,
        existing_server_default="PENDING",
    )

    # 2. Add recovery tracking columns
    op.add_column("social_posts", sa.Column("recovered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("social_posts", sa.Column("recovery_notes", sa.Text(), nullable=True))

    # 3. Add composite index for stale publishing queries
    op.create_index(
        "ix_social_posts_status_updated_at",
        "social_posts",
        ["status", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_social_posts_status_updated_at", table_name="social_posts")
    op.drop_column("social_posts", "recovery_notes")
    op.drop_column("social_posts", "recovered_at")
    op.alter_column(
        "social_posts",
        "status",
        existing_type=sa.String(length=32),
        type_=sa.String(length=20),
        existing_nullable=False,
        existing_server_default="PENDING",
    )
