"""Create email subscriber, newsletter campaign, and delivery tracking tables

Revision ID: 0008_email_newsletter
Revises: 0007_stale_recovery
Create Date: 2026-11-08 00:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic (max 32 chars for alembic_version)
revision: str = "0008_email_newsletter"
down_revision: Union[str, None] = "0007_stale_recovery"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Email Subscribers
    op.create_table(
        "email_subscribers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("email_normalized", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("verification_token_hash", sa.String(length=64), nullable=True),
        sa.Column("verification_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unsubscribe_token_hash", sa.String(length=64), nullable=False),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
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
        "ix_email_subscribers_email_normalized",
        "email_subscribers",
        ["email_normalized"],
        unique=True,
    )
    op.create_index(
        "ix_email_subscribers_status",
        "email_subscribers",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_email_subscribers_verification_token_hash",
        "email_subscribers",
        ["verification_token_hash"],
        unique=False,
    )
    op.create_index(
        "ix_email_subscribers_unsubscribe_token_hash",
        "email_subscribers",
        ["unsubscribe_token_hash"],
        unique=True,
    )

    # 2. Newsletter Campaigns
    op.create_table(
        "newsletter_campaigns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("article_ids", sa.JSON(), nullable=False),
        sa.Column("recipient_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("delivered_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
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
        "ix_newsletter_campaigns_scheduled_for",
        "newsletter_campaigns",
        ["scheduled_for"],
        unique=False,
    )
    op.create_index(
        "ix_newsletter_campaigns_status",
        "newsletter_campaigns",
        ["status"],
        unique=False,
    )

    # 3. Newsletter Deliveries
    op.create_table(
        "newsletter_deliveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("subscriber_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["newsletter_campaigns.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscriber_id"],
            ["email_subscribers.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "subscriber_id", name="uq_campaign_subscriber"),
    )
    op.create_index(
        "ix_newsletter_deliveries_campaign_id",
        "newsletter_deliveries",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        "ix_newsletter_deliveries_subscriber_id",
        "newsletter_deliveries",
        ["subscriber_id"],
        unique=False,
    )
    op.create_index(
        "ix_newsletter_deliveries_status",
        "newsletter_deliveries",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("newsletter_deliveries")
    op.drop_table("newsletter_campaigns")
    op.drop_table("email_subscribers")
