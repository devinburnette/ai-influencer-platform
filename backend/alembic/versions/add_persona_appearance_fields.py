"""Add persona appearance fields for image generation.

Revision ID: add_persona_appearance
Revises: b3f31879eb98
Create Date: 2026-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_persona_appearance'
down_revision = 'add_nsfw_content_support'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add appearance fields to personas table
    op.add_column('personas', sa.Column(
        'appearance_ethnicity',
        sa.String(100),
        nullable=True,
        server_default='mixed race'
    ))
    op.add_column('personas', sa.Column(
        'appearance_age',
        sa.String(50),
        nullable=True,
        server_default='25 years old'
    ))
    op.add_column('personas', sa.Column(
        'appearance_hair',
        sa.String(200),
        nullable=True,
        server_default='curly, naturally styled hair with blonde highlights'
    ))
    op.add_column('personas', sa.Column(
        'appearance_body_type',
        sa.String(100),
        nullable=True,
        server_default='fit and toned'
    ))
    
    # Backfill existing personas with default values
    op.execute("""
        UPDATE personas 
        SET 
            appearance_ethnicity = 'mixed race',
            appearance_age = '25 years old',
            appearance_hair = 'curly, naturally styled hair with blonde highlights',
            appearance_body_type = 'fit and toned'
        WHERE appearance_ethnicity IS NULL
    """)


def downgrade() -> None:
    op.drop_column('personas', 'appearance_body_type')
    op.drop_column('personas', 'appearance_hair')
    op.drop_column('personas', 'appearance_age')
    op.drop_column('personas', 'appearance_ethnicity')
