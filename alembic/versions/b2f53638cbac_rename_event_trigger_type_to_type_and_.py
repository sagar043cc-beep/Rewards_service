"""rename event trigger_type to type and add sort_order column

Revision ID: b2f53638cbac
Revises: 66fdbbc4c49e
Create Date: 2026-05-11 09:17:37.386640+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f53638cbac'
down_revision: Union[str, None] = '66fdbbc4c49e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename trigger_type → type
    op.alter_column('events', 'trigger_type', new_column_name='type')

    # Drop old CHECK constraint on trigger_type (conventional name)
    op.execute('ALTER TABLE events DROP CONSTRAINT IF EXISTS events_trigger_type_check')

    # Migrate data: map old values to new set
    op.execute("UPDATE events SET type = 'static' WHERE type = 'SINGLE_TRIGGER'")
    op.execute("UPDATE events SET type = 'action' WHERE type = 'RULE_BASED'")

    # Add new CHECK constraint on type: only 'static' or 'action'
    op.create_check_constraint(
        'ck_events_type',
        'events',
        "type IN ('static', 'action')"
    )

    # Add sort_order column (nullable, no default)
    op.add_column('events', sa.Column('sort_order', sa.Integer(), nullable=True))


def downgrade() -> None:
    # Remove sort_order
    op.drop_column('events', 'sort_order')

    # Drop CHECK constraint on type
    op.drop_constraint('ck_events_type', 'events')

    # Reverse data migration
    op.execute("UPDATE events SET type = 'SINGLE_TRIGGER' WHERE type = 'static'")
    op.execute("UPDATE events SET type = 'RULE_BASED' WHERE type = 'action'")

    # Rename type → trigger_type
    op.alter_column('events', 'type', new_column_name='trigger_type')

    # Recreate original CHECK constraint on trigger_type
    op.create_check_constraint(
        'ck_events_trigger_type',
        'events',
        "trigger_type IN ('SINGLE_TRIGGER', 'RULE_BASED')"
    )
