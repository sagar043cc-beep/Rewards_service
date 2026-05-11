"""initial migration

Revision ID: 6ec018de4420
Revises: 
Create Date: 2026-05-08 10:52:50.902520+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6ec018de4420'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============ TENANCY ============
    op.execute("""
    CREATE TABLE tenants (
      id              UUID PRIMARY KEY,
      slug            TEXT UNIQUE NOT NULL,
      default_currency CHAR(3) NOT NULL DEFAULT 'INR',
      created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    # ============ CATALOG OF REWARDS (the "what") ============
    op.execute("""
    CREATE TABLE rewards (
      id            UUID PRIMARY KEY,
      tenant_id     UUID NOT NULL REFERENCES tenants(id),
      name          TEXT NOT NULL,
      type          TEXT NOT NULL CHECK (type IN ('WALLET','PACKAGE','BADGE','XP')),
      payload       JSONB NOT NULL,
      is_active     BOOLEAN NOT NULL DEFAULT TRUE,
      created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, name)
    );
    """)
    op.execute("CREATE INDEX ON rewards (tenant_id, type) WHERE is_active;")

    # Master tables for badge/package references (sketch)
    op.execute("""
    CREATE TABLE badges (
      id UUID PRIMARY KEY,
      tenant_id UUID,
      name TEXT,
      icon_url TEXT
    );
    """)
    op.execute("""
    CREATE TABLE packages (
      id UUID PRIMARY KEY,
      tenant_id UUID,
      name TEXT,
      price NUMERIC
    );
    """)

    # ============ EVENTS / CAMPAIGNS (the container) ============
    op.execute("""
    CREATE TABLE events (
      id              UUID PRIMARY KEY,
      tenant_id       UUID NOT NULL REFERENCES tenants(id),
      code            TEXT NOT NULL,
      name            TEXT NOT NULL,
      trigger_type    TEXT NOT NULL CHECK (trigger_type IN ('SINGLE_TRIGGER','RULE_BASED')),
      starts_at       TIMESTAMPTZ NOT NULL,
      ends_at         TIMESTAMPTZ NOT NULL,
      max_participants INT,
      per_user_cap    INT NOT NULL DEFAULT 1,
      status          TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','ACTIVE','PAUSED','ENDED')),
      created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
      UNIQUE (tenant_id, code),
      CHECK (ends_at > starts_at)
    );
    """)
    op.execute("CREATE INDEX ON events (tenant_id, status, starts_at, ends_at);")

    # ============ CONDITIONS for RULE_BASED events ============
    op.execute("""
    CREATE TABLE event_conditions (
      id              UUID PRIMARY KEY,
      event_id        UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
      tenant_id       UUID NOT NULL,
      action_type     TEXT NOT NULL,
      threshold_count INT NOT NULL CHECK (threshold_count >= 1),
      window_seconds  INT,
      filters         JSONB NOT NULL DEFAULT '{}'::jsonb,
      logical_group   INT NOT NULL DEFAULT 1
    );
    """)
    op.execute("CREATE INDEX ON event_conditions (tenant_id, action_type);")

    # ============ REWARDS attached to EVENTS ============
    op.execute("""
    CREATE TABLE event_rewards (
      event_id    UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
      reward_id   UUID NOT NULL REFERENCES rewards(id),
      tier        INT NOT NULL DEFAULT 1,
      PRIMARY KEY (event_id, reward_id, tier)
    );
    """)

    # ============ USER ACTION LEDGER (the source of truth) ============
    op.execute("""
    CREATE TABLE user_actions (
      id            BIGSERIAL PRIMARY KEY,
      tenant_id     UUID NOT NULL,
      user_id       UUID NOT NULL,
      action_type   TEXT NOT NULL,
      occurred_at   TIMESTAMPTZ NOT NULL,
      reference_id  UUID,
      attributes    JSONB NOT NULL DEFAULT '{}'::jsonb,
      reversed_at   TIMESTAMPTZ,
      reversal_of   BIGINT REFERENCES user_actions(id)
    );
    """)
    op.execute("CREATE INDEX ON user_actions (tenant_id, user_id, action_type, occurred_at) WHERE reversed_at IS NULL;")

    # ============ PARTICIPATION + PROGRESS ============
    op.execute("""
    CREATE TABLE event_participations (
      id              UUID PRIMARY KEY,
      tenant_id       UUID NOT NULL,
      event_id        UUID NOT NULL REFERENCES events(id),
      user_id         UUID NOT NULL,
      status          TEXT NOT NULL DEFAULT 'IN_PROGRESS' CHECK (status IN ('IN_PROGRESS','COMPLETED','FAILED','EXPIRED')),
      enrolled_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
      completed_at    TIMESTAMPTZ,
      UNIQUE (tenant_id, event_id, user_id)
    );
    """)

    op.execute("""
    CREATE TABLE event_progress (
      participation_id UUID NOT NULL REFERENCES event_participations(id) ON DELETE CASCADE,
      condition_id     UUID NOT NULL REFERENCES event_conditions(id),
      current_count    INT NOT NULL DEFAULT 0,
      last_action_at   TIMESTAMPTZ,
      satisfied        BOOLEAN NOT NULL DEFAULT FALSE,
      PRIMARY KEY (participation_id, condition_id)
    );
    """)

    # ============ ACTUAL REWARD GRANTS (the "who got it") ============
    op.execute("""
    CREATE TABLE reward_grants (
      id                UUID PRIMARY KEY,
      tenant_id         UUID NOT NULL,
      user_id           UUID NOT NULL,
      reward_id         UUID NOT NULL REFERENCES rewards(id),
      source_type       TEXT NOT NULL CHECK (source_type IN ('EVENT','MANUAL','RULE')),
      source_event_id   UUID REFERENCES events(id),
      granted_by        UUID,
      status            TEXT NOT NULL DEFAULT 'GRANTED' CHECK (status IN ('GRANTED','CLAIMED','EXPIRED','REVOKED')),
      granted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
      claimed_at        TIMESTAMPTZ,
      expires_at        TIMESTAMPTZ,
      idempotency_key   TEXT NOT NULL,
      UNIQUE (tenant_id, idempotency_key)
    );
    """)
    op.execute("CREATE INDEX ON reward_grants (tenant_id, user_id, status);")

    # ============ SIDE-EFFECT TABLES (downstream of grants) ============
    op.execute("""
    CREATE TABLE wallet_transactions (
      id            UUID PRIMARY KEY,
      tenant_id     UUID NOT NULL,
      user_id       UUID NOT NULL,
      amount        NUMERIC(12,2) NOT NULL,
      currency      CHAR(3) NOT NULL,
      grant_id      UUID REFERENCES reward_grants(id),
      kind          TEXT NOT NULL,
      created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """)

    op.execute("""
    CREATE TABLE user_badges (
      tenant_id  UUID NOT NULL,
      user_id    UUID NOT NULL,
      badge_id   UUID NOT NULL REFERENCES badges(id),
      grant_id   UUID REFERENCES reward_grants(id),
      earned_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
      PRIMARY KEY (tenant_id, user_id, badge_id)
    );
    """)

    op.execute("""
    CREATE TABLE user_xp (
      tenant_id  UUID NOT NULL,
      user_id    UUID NOT NULL,
      total_xp   BIGINT NOT NULL DEFAULT 0,
      PRIMARY KEY (tenant_id, user_id)
    );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_xp;")
    op.execute("DROP TABLE IF EXISTS user_badges;")
    op.execute("DROP TABLE IF EXISTS wallet_transactions;")
    op.execute("DROP TABLE IF EXISTS reward_grants;")
    op.execute("DROP TABLE IF EXISTS event_progress;")
    op.execute("DROP TABLE IF EXISTS event_participations;")
    op.execute("DROP TABLE IF EXISTS user_actions;")
    op.execute("DROP TABLE IF EXISTS event_rewards;")
    op.execute("DROP TABLE IF EXISTS event_conditions;")
    op.execute("DROP TABLE IF EXISTS events;")
    op.execute("DROP TABLE IF EXISTS packages;")
    op.execute("DROP TABLE IF EXISTS badges;")
    op.execute("DROP TABLE IF EXISTS rewards;")
    op.execute("DROP TABLE IF EXISTS tenants;")
