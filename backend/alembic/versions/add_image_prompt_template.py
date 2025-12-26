"""Add image prompt template to personas

Revision ID: add_image_prompt_template
Revises: add_prompt_templates
Create Date: 2024-12-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_image_prompt_template'
down_revision = 'add_prompt_templates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('personas', sa.Column('image_prompt_template', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('personas', 'image_prompt_template')

