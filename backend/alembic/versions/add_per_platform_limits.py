"""Add per-platform daily posting limits

Revision ID: add_per_platform_limits
Revises: add_fanvue_platform
Create Date: 2026-01-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_per_platform_limits'
down_revision: Union[str, None] = 'remove_unsupported_platforms'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add per-platform daily rate limit tracking columns to platform_accounts
    op.add_column('platform_accounts', sa.Column('posts_today', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('platform_accounts', sa.Column('video_posts_today', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('platform_accounts', sa.Column('stories_today', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('platform_accounts', sa.Column('reels_today', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('platform_accounts', sa.Column('last_limit_reset', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove the columns
    op.drop_column('platform_accounts', 'posts_today')
    op.drop_column('platform_accounts', 'video_posts_today')
    op.drop_column('platform_accounts', 'stories_today')
    op.drop_column('platform_accounts', 'reels_today')
    op.drop_column('platform_accounts', 'last_limit_reset')

