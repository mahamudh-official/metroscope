"""add full_text and content_display_authorized columns to news_articles

Revision ID: 0012_article_full_text_rights
Revises: 0011_drop_country_server_default
Create Date: 2026-11-13 11:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0012_article_full_text_rights"
down_revision: Union[str, None] = "0011_drop_country_server_default"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add full_text nullable column for raw root-level Webz.io article body
    op.add_column(
        "news_articles",
        sa.Column("full_text", sa.Text(), nullable=True),
    )
    # 2. Add content_display_authorized boolean column with default false
    op.add_column(
        "news_articles",
        sa.Column(
            "content_display_authorized",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("news_articles", "content_display_authorized")
    op.drop_column("news_articles", "full_text")
