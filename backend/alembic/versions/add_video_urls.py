"""Add video_urls column to content table

Revision ID: add_video_urls
Revises: add_image_prompt_template
Create Date: 2024-12-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'add_video_urls'
down_revision = 'add_image_prompt_template'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('content', sa.Column('video_urls', postgresql.ARRAY(sa.String()), nullable=True, server_default='{}'))


def downgrade() -> None:
    op.drop_column('content', 'video_urls')

