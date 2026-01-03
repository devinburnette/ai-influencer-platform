"""Add Fanvue platform support

Revision ID: add_fanvue_platform
Revises: b3f31879eb98
Create Date: 2025-12-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_fanvue_platform'
down_revision: Union[str, None] = 'b3f31879eb98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'FANVUE' to the platform enum (uppercase to match SQLAlchemy enum naming)
    # PostgreSQL requires us to add the new value to the existing enum type
    connection = op.get_bind()
    
    # Check if 'FANVUE' already exists in the enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_enum WHERE enumlabel = 'FANVUE' AND enumtypid = "
        "(SELECT oid FROM pg_type WHERE typname = 'platform')"
    ))
    
    if not result.fetchone():
        # Add FANVUE to the platform enum
        op.execute("ALTER TYPE platform ADD VALUE IF NOT EXISTS 'FANVUE'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing values from enums easily
    # The 'fanvue' value will remain in the enum but won't be used
    # To fully remove it, you would need to recreate the enum type
    pass

