"""update event_conditions for action event payload

Revision ID: f3a7c2d9b1e4
Revises: e1f2a3b4c5d6
Create Date: 2026-05-14 00:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f3a7c2d9b1e4"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_table("event_conditions"):
        op.create_table(
            "event_conditions",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("action_type", sa.String(), nullable=False),
            sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("qty", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_event_conditions_event_id", "event_conditions", ["event_id"], unique=False)
        return

    if _has_column("event_conditions", "logical_group") and not _has_column("event_conditions", "qty"):
        op.alter_column("event_conditions", "logical_group", new_column_name="qty")

    if not _has_column("event_conditions", "qty"):
        op.add_column("event_conditions", sa.Column("qty", sa.Integer(), nullable=True))

    if not _has_column("event_conditions", "filters"):
        op.add_column(
            "event_conditions",
            sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )

    if _has_column("event_conditions", "tenant_id"):
        op.alter_column("event_conditions", "tenant_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    if _has_column("event_conditions", "threshold_count"):
        op.alter_column("event_conditions", "threshold_count", existing_type=sa.Integer(), nullable=True)
    if _has_column("event_conditions", "filters"):
        op.alter_column(
            "event_conditions",
            "filters",
            existing_type=postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        )
    if _has_column("event_conditions", "qty"):
        op.alter_column("event_conditions", "qty", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Restore old column name only if it matches the prior state.
    if _has_table("event_conditions"):
        if _has_column("event_conditions", "qty") and not _has_column("event_conditions", "logical_group"):
            op.alter_column("event_conditions", "qty", new_column_name="logical_group")
