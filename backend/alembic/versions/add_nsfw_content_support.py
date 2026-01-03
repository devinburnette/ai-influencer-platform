"""Add NSFW content support for Fanvue

Revision ID: add_nsfw_content_support
Revises: b3f31879eb98_add_generation_tracking_columns
Create Date: 2026-01-02

This migration adds support for NSFW content generation:
- nsfw_posts_today: Daily counter for NSFW content
- nsfw_prompt_template: Custom prompt template for NSFW content
- nsfw_reference_images: Reference image URLs for Seedream 4 generation
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'add_nsfw_content_support'
down_revision = 'add_per_platform_limits'
branch_labels = None
depends_on = None


def upgrade():
    """Add NSFW content support columns to personas table."""
    # Add nsfw_posts_today counter
    op.add_column(
        'personas',
        sa.Column('nsfw_posts_today', sa.Integer(), nullable=True, server_default='0')
    )
    
    # Add NSFW prompt template
    op.add_column(
        'personas',
        sa.Column('nsfw_prompt_template', sa.Text(), nullable=True)
    )
    
    # Add reference images array for NSFW content generation
    op.add_column(
        'personas',
        sa.Column(
            'nsfw_reference_images',
            postgresql.ARRAY(sa.String()),
            nullable=True,
            server_default='{}'
        )
    )
    
    # Update existing rows to have default values
    op.execute("UPDATE personas SET nsfw_posts_today = 0 WHERE nsfw_posts_today IS NULL")
    op.execute("UPDATE personas SET nsfw_reference_images = '{}' WHERE nsfw_reference_images IS NULL")


def downgrade():
    """Remove NSFW content support columns from personas table."""
    op.drop_column('personas', 'nsfw_reference_images')
    op.drop_column('personas', 'nsfw_prompt_template')
    op.drop_column('personas', 'nsfw_posts_today')

