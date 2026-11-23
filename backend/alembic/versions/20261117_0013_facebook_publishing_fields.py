"""Add photo post, comment, and metadata fields to social_posts

Revision ID: 0013_facebook_publishing_fields
Revises: 0012_article_full_text_rights
Create Date: 2026-11-17 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision: str = "0013_facebook_publishing_fields"
down_revision: Union[str, None] = "0012_article_full_text_rights"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("social_posts", sa.Column("post_type", sa.String(length=20), nullable=True, server_default="photo"))
    op.add_column("social_posts", sa.Column("external_photo_id", sa.String(length=128), nullable=True))
    op.add_column("social_posts", sa.Column("external_comment_id", sa.String(length=128), nullable=True))
    op.add_column("social_posts", sa.Column("comment_content", sa.Text(), nullable=True))
    op.add_column("social_posts", sa.Column("extra_metadata", sa.Text(), nullable=True))

    op.create_index("ix_social_posts_external_photo_id", "social_posts", ["external_photo_id"], unique=False)
    op.create_index("ix_social_posts_external_comment_id", "social_posts", ["external_comment_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_social_posts_external_comment_id", table_name="social_posts")
    op.drop_index("ix_social_posts_external_photo_id", table_name="social_posts")
    op.drop_column("social_posts", "extra_metadata")
    op.drop_column("social_posts", "comment_content")
    op.drop_column("social_posts", "external_comment_id")
    op.drop_column("social_posts", "external_photo_id")
    op.drop_column("social_posts", "post_type")
