"""drop forced US server_default on article and source country columns

Revision ID: 0011_drop_country_server_default
Revises: 493f6e6a0c63
Create Date: 2026-11-12 06:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0011_drop_country_server_default"
down_revision: Union[str, None] = "493f6e6a0c63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "news_articles",
        "country",
        existing_type=sa.String(length=10),
        nullable=True,
        server_default=None,
    )
    op.alter_column(
        "news_sources",
        "country",
        existing_type=sa.String(length=10),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    op.alter_column(
        "news_sources",
        "country",
        existing_type=sa.String(length=10),
        nullable=True,
        server_default="US",
    )
    op.alter_column(
        "news_articles",
        "country",
        existing_type=sa.String(length=10),
        nullable=True,
        server_default="US",
    )
