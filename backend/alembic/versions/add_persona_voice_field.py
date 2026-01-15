"""Add persona voice field for video generation.

Revision ID: add_persona_voice
Revises: add_persona_appearance
Create Date: 2026-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_persona_voice'
down_revision = 'add_persona_appearance'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add voice/accent field to personas table
    op.add_column('personas', sa.Column(
        'appearance_voice',
        sa.String(100),
        nullable=True,
        server_default='American'
    ))
    
    # Backfill existing personas with American accent
    op.execute("""
        UPDATE personas 
        SET appearance_voice = 'American'
        WHERE appearance_voice IS NULL
    """)


def downgrade() -> None:
    op.drop_column('personas', 'appearance_voice')
