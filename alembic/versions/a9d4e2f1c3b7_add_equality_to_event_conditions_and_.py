"""add equality to event_conditions and reward_id to events

Revision ID: a9d4e2f1c3b7
Revises: f3a7c2d9b1e4
Create Date: 2026-05-15 00:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a9d4e2f1c3b7"
down_revision: Union[str, None] = "f3a7c2d9b1e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("event_conditions", sa.Column("equality", sa.String(), nullable=True))

    op.add_column("events", sa.Column("reward_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_events_reward_id_rewards",
        "events",
        "rewards",
        ["reward_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_events_reward_id_rewards", "events", type_="foreignkey")
    op.drop_column("events", "reward_id")

    op.drop_column("event_conditions", "equality")

