"""Add per-platform engagement and posting control

Revision ID: add_platform_engagement_control
Revises: add_app_settings
Create Date: 2024-12-25
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_platform_engagement_control'
down_revision = 'add_app_settings'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add engagement_paused column to control per-platform engagement
    op.add_column(
        'platform_accounts',
        sa.Column('engagement_paused', sa.Boolean, server_default='false', nullable=False)
    )
    
    # Add posting_paused column to control per-platform posting
    op.add_column(
        'platform_accounts',
        sa.Column('posting_paused', sa.Boolean, server_default='false', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('platform_accounts', 'posting_paused')
    op.drop_column('platform_accounts', 'engagement_paused')

