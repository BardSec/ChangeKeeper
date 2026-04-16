"""Add change_type column for quick log vs full change

Revision ID: 002_add_change_type
Revises: 001_initial
Create Date: 2026-04-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_change_type'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum type first
    op.execute("CREATE TYPE changetypeenum AS ENUM ('quick', 'full')")

    # Add column with server_default so existing rows get 'full'
    op.add_column(
        'changes',
        sa.Column(
            'change_type',
            sa.Enum('quick', 'full', name='changetypeenum', create_type=False),
            nullable=False,
            server_default=sa.text("'full'"),
        )
    )

    op.create_index(op.f('ix_changes_change_type'), 'changes', ['change_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_changes_change_type'), table_name='changes')
    op.drop_column('changes', 'change_type')
    op.execute("DROP TYPE changetypeenum")
