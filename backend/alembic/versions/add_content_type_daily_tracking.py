"""Add daily tracking for video posts, stories, and reels

Revision ID: add_content_type_daily_tracking
Revises: 2295ff28d4ed
Create Date: 2024-12-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_content_type_daily_tracking'
down_revision: Union[str, None] = '2295ff28d4ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add daily tracking columns for content types
    op.add_column('personas', sa.Column('video_posts_today', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('personas', sa.Column('stories_today', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('personas', sa.Column('reels_today', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('personas', 'reels_today')
    op.drop_column('personas', 'stories_today')
    op.drop_column('personas', 'video_posts_today')

