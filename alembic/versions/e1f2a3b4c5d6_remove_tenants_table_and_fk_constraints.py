"""Remove tenants table and foreign key constraints

Revision ID: e1f2a3b4c5d6
Revises: d94114a8744d
Create Date: 2026-05-12 12:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = '86a2270e615a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop foreign key constraints and tenants table."""
    # Drop foreign key constraint from rewards table
    op.execute("ALTER TABLE rewards DROP CONSTRAINT IF EXISTS rewards_tenant_id_fkey;")
    
    # Drop foreign key constraint from events table
    op.execute("ALTER TABLE events DROP CONSTRAINT IF EXISTS events_tenant_id_fkey;")
    
    # Drop foreign key constraint from event_conditions table
    op.execute("ALTER TABLE event_conditions DROP CONSTRAINT IF EXISTS event_conditions_tenant_id_fkey;")
    
    # Drop the tenants table
    op.drop_table('tenants')


def downgrade() -> None:
    """Recreate tenants table and foreign key constraints."""
    # Recreate tenants table
    op.execute("""
    CREATE TABLE tenants (
      id              UUID PRIMARY KEY,
      slug            TEXT UNIQUE NOT NULL,
      default_currency CHAR(3) NOT NULL DEFAULT 'INR',
      created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)
    
    # Recreate foreign key constraint for rewards
    op.execute("ALTER TABLE rewards ADD CONSTRAINT rewards_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id);")
    
    # Recreate foreign key constraint for events
    op.execute("ALTER TABLE events ADD CONSTRAINT events_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id);")
    
    # Recreate foreign key constraint for event_conditions
    op.execute("ALTER TABLE event_conditions ADD CONSTRAINT event_conditions_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenants(id);")
