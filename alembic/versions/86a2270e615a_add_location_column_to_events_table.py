"""add location column to events table

Revision ID: 86a2270e615a
Revises: 1b129c225247
Create Date: 2026-05-11 12:24:43.352815+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '86a2270e615a'
down_revision: Union[str, None] = '1b129c225247'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename url column to location
    op.alter_column('events', 'url', new_column_name='location')


def downgrade() -> None:
    # Rename location column back to url
    op.alter_column('events', 'location', new_column_name='url')
