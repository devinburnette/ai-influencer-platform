"""Add platform account stats columns

Revision ID: add_platform_account_stats
Revises: add_platform_engagement_control
Create Date: 2024-12-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_platform_account_stats'
down_revision = 'add_platform_engagement_control'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add follower_count, following_count, post_count to platform_accounts
    op.add_column('platform_accounts', sa.Column('follower_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('platform_accounts', sa.Column('following_count', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('platform_accounts', sa.Column('post_count', sa.Integer(), nullable=True, server_default='0'))


def downgrade() -> None:
    op.drop_column('platform_accounts', 'post_count')
    op.drop_column('platform_accounts', 'following_count')
    op.drop_column('platform_accounts', 'follower_count')

