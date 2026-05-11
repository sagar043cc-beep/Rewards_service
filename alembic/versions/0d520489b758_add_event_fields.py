"""add event fields

Revision ID: 0d520489b758
Revises: 6ec018de4420
Create Date: 2026-05-08 11:09:51.276407+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0d520489b758'
down_revision: Union[str, None] = '6ec018de4420'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('events', sa.Column('image', sa.Text(), nullable=True))
    op.add_column('events', sa.Column('url', sa.Text(), nullable=True))
    op.add_column('events', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('events', sa.Column('btn_name', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('events', 'btn_name')
    op.drop_column('events', 'description')
    op.drop_column('events', 'url')
    op.drop_column('events', 'image')
