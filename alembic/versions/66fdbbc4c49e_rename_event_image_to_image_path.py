"""rename event image to image_path

Revision ID: 66fdbbc4c49e
Revises: 6c7008c1b807
Create Date: 2026-05-11 06:50:29.487665+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '66fdbbc4c49e'
down_revision: Union[str, None] = '6c7008c1b807'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('events', 'image', new_column_name='image_path')


def downgrade() -> None:
    op.alter_column('events', 'image_path', new_column_name='image')
