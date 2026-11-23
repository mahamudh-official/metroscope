"""allow unknown article and source countries

Revision ID: 493f6e6a0c63
Revises: 0010_webz_field_expansion
Create Date: 2026-11-11 13:02:59.568693

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '493f6e6a0c63'
down_revision: Union[str, None] = '0010_webz_field_expansion'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "news_articles",
        "country",
        existing_type=sa.String(length=10),
        nullable=True,
    )
    op.alter_column(
        "news_sources",
        "country",
        existing_type=sa.String(length=10),
        nullable=True,
    )


def downgrade() -> None:
    # Do not silently convert unknown countries into "US".
    # Downgrade will fail safely if NULL values exist.
    op.alter_column(
        "news_sources",
        "country",
        existing_type=sa.String(length=10),
        nullable=False,
    )
    op.alter_column(
        "news_articles",
        "country",
        existing_type=sa.String(length=10),
        nullable=False,
    )
