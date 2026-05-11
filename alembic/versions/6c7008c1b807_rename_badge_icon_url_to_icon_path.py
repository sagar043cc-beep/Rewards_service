"""rename badge icon_url to icon_path

Revision ID: 6c7008c1b807
Revises: 0d520489b758
Create Date: 2026-05-11 06:19:36.426392+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c7008c1b807'
down_revision: Union[str, None] = '0d520489b758'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('badges', 'icon_url', new_column_name='icon_path')


def downgrade() -> None:
    op.alter_column('badges', 'icon_path', new_column_name='icon_url')
