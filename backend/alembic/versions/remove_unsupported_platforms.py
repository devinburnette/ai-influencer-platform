"""Remove unsupported platforms (tiktok, youtube)

Revision ID: remove_unsupported_platforms
Revises: add_fanvue_platform
Create Date: 2025-12-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'remove_unsupported_platforms'
down_revision: Union[str, None] = 'add_fanvue_platform'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Note: tiktok and youtube were removed from the Python enum
    # but they may never have existed in the database enum.
    # PostgreSQL doesn't support removing values from enums easily,
    # so we just leave them if they exist.
    # No action needed here - the enum values are only in Python code.
    pass


def downgrade() -> None:
    # Nothing to do
    pass
