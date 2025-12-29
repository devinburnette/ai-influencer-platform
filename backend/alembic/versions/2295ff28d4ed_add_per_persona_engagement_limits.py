"""add_per_persona_engagement_limits

Revision ID: 2295ff28d4ed
Revises: add_dm_support
Create Date: 2025-12-29 19:33:09.176132

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2295ff28d4ed'
down_revision: Union[str, None] = 'add_dm_support'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add per-persona engagement limit columns
    op.add_column('personas', sa.Column('max_likes_per_day', sa.Integer(), nullable=True))
    op.add_column('personas', sa.Column('max_comments_per_day', sa.Integer(), nullable=True))
    op.add_column('personas', sa.Column('max_follows_per_day', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('personas', 'max_follows_per_day')
    op.drop_column('personas', 'max_comments_per_day')
    op.drop_column('personas', 'max_likes_per_day')
