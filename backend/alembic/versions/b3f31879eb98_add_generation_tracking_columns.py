"""add_generation_tracking_columns

Revision ID: b3f31879eb98
Revises: add_content_type_daily_tracking
Create Date: 2025-12-30 23:14:20.087136

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3f31879eb98'
down_revision: Union[str, None] = 'add_content_type_daily_tracking'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add generation tracking columns to personas
    op.add_column('personas', sa.Column('videos_generated_today', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('personas', sa.Column('images_generated_today', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('personas', 'images_generated_today')
    op.drop_column('personas', 'videos_generated_today')
