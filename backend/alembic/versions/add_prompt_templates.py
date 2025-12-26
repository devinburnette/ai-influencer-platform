"""Add custom prompt templates to personas

Revision ID: add_prompt_templates
Revises: add_platform_account_stats
Create Date: 2024-12-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_prompt_templates'
down_revision = 'add_platform_account_stats'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add content_prompt_template and comment_prompt_template to personas
    op.add_column('personas', sa.Column('content_prompt_template', sa.Text(), nullable=True))
    op.add_column('personas', sa.Column('comment_prompt_template', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('personas', 'comment_prompt_template')
    op.drop_column('personas', 'content_prompt_template')

