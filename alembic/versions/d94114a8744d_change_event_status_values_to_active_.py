"""change event status values to active/inactive/draft

Revision ID: d94114a8744d
Revises: b2f53638cbac
Create Date: 2026-05-11 09:29:41.476059+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd94114a8744d'
down_revision: Union[str, None] = 'b2f53638cbac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize existing status values to new set
    op.execute("UPDATE events SET status = 'draft' WHERE status = 'DRAFT'")
    op.execute("UPDATE events SET status = 'active' WHERE status = 'ACTIVE'")
    op.execute("UPDATE events SET status = 'inactive' WHERE status IN ('PAUSED', 'ENDED')")

    # Drop old CHECK constraint (auto-generated name likely events_status_check)
    op.execute('ALTER TABLE events DROP CONSTRAINT IF EXISTS events_status_check')

    # Add new CHECK constraint allowing only the new values
    op.create_check_constraint(
        'ck_events_status',
        'events',
        "status IN ('active', 'inactive', 'draft')"
    )


def downgrade() -> None:
    # Drop new constraint
    op.drop_constraint('ck_events_status', 'events')

    # Reverse mapping
    op.execute("UPDATE events SET status = 'DRAFT' WHERE status = 'draft'")
    op.execute("UPDATE events SET status = 'ACTIVE' WHERE status = 'active'")
    # Map inactive back to PAUSED (original had both PAUSED and ENDED; choose PAUSED)
    op.execute("UPDATE events SET status = 'PAUSED' WHERE status = 'inactive'")

    # Recreate original CHECK constraint (DRAFT, ACTIVE, PAUSED, ENDED)
    op.create_check_constraint(
        'events_status_check',
        'events',
        "status IN ('DRAFT', 'ACTIVE', 'PAUSED', 'ENDED')"
    )
