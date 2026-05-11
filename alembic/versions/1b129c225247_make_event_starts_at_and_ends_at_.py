"""make event starts_at and ends_at nullable

Revision ID: 1b129c225247
Revises: d94114a8744d
Create Date: 2026-05-11 09:44:10.482114+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b129c225247'
down_revision: Union[str, None] = 'd94114a8744d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('events', 'starts_at', existing_type=sa.DateTime(), nullable=True)
    op.alter_column('events', 'ends_at', existing_type=sa.DateTime(), nullable=True)


def downgrade() -> None:
    # Ensure no NULL values exist before enforcing NOT NULL
    op.execute("UPDATE events SET starts_at = now() WHERE starts_at IS NULL")
    op.execute("UPDATE events SET ends_at = now() WHERE ends_at IS NULL")
    op.alter_column('events', 'starts_at', existing_type=sa.DateTime(), nullable=False)
    op.alter_column('events', 'ends_at', existing_type=sa.DateTime(), nullable=False)
