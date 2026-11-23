"""Migrate to Webz.io single provider news acquisition and usage ledger

Revision ID: 0009_webz_io_migration
Revises: 0008_email_newsletter
Create Date: 2026-11-10 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = "0009_webz_io_migration"
down_revision: Union[str, None] = "0008_email_newsletter"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add Webz.io article metadata fields to news_articles table
    op.add_column("news_articles", sa.Column("uuid", sa.String(length=100), nullable=True))
    op.add_column("news_articles", sa.Column("author", sa.String(length=255), nullable=True))
    op.add_column("news_articles", sa.Column("topics", sa.Text(), nullable=True))
    op.add_column("news_articles", sa.Column("trust_indicators", sa.Text(), nullable=True))
    op.add_column("news_articles", sa.Column("image_metadata", sa.Text(), nullable=True))

    op.create_index(
        "ix_news_articles_uuid",
        "news_articles",
        ["uuid"],
        unique=True,
    )

    # 2. Create durable PostgreSQL-backed Webz.io usage and budget ledger
    op.create_table(
        "webz_usage_ledger",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("billing_period", sa.String(length=20), nullable=False),
        sa.Column("job_name", sa.String(length=100), nullable=False),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("query_params", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("returned_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("billable_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("estimated_cost", sa.Numeric(precision=10, scale=4), server_default="0.0050", nullable=False),
        sa.Column("actual_cost", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("reserved_cost", sa.Numeric(precision=10, scale=4), server_default="0.0050", nullable=False),
        sa.Column("requests_left", sa.Integer(), nullable=True),
        sa.Column("credits_used", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("remaining_allowance", sa.Numeric(precision=10, scale=4), server_default="4.0000", nullable=False),
        sa.Column("stop_reason", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_webz_usage_ledger_billing_period",
        "webz_usage_ledger",
        ["billing_period"],
        unique=False,
    )
    op.create_index(
        "ix_webz_usage_ledger_job_name",
        "webz_usage_ledger",
        ["job_name"],
        unique=False,
    )
    op.create_index(
        "ix_webz_ledger_period_created",
        "webz_usage_ledger",
        ["billing_period", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_webz_ledger_period_created", table_name="webz_usage_ledger")
    op.drop_index("ix_webz_usage_ledger_job_name", table_name="webz_usage_ledger")
    op.drop_index("ix_webz_usage_ledger_billing_period", table_name="webz_usage_ledger")
    op.drop_table("webz_usage_ledger")

    op.drop_index("ix_news_articles_uuid", table_name="news_articles")
    op.drop_column("news_articles", "image_metadata")
    op.drop_column("news_articles", "trust_indicators")
    op.drop_column("news_articles", "topics")
    op.drop_column("news_articles", "author")
    op.drop_column("news_articles", "uuid")
