"""Add posted_platforms column to content

Revision ID: add_posted_platforms
Revises: 
Create Date: 2024-12-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


# revision identifiers, used by Alembic.
revision = 'add_posted_platforms'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add posted_platforms column to track which platforms have received this content
    op.add_column(
        'content',
        sa.Column('posted_platforms', ARRAY(sa.String), server_default='{}', nullable=True)
    )


def downgrade() -> None:
    op.drop_column('content', 'posted_platforms')

