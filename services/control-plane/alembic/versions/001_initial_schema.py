"""Initial schema: missions, events, approvals, receipts, workers, integrations, cost_events, surface_sessions.

Revision ID: 001_initial
Revises:
Create Date: 2026-04-07

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "missions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False, server_default="pending"),
        sa.Column("priority", sa.String(length=32), nullable=False, server_default="normal"),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("surface_origin", sa.String(length=256), nullable=True),
        sa.Column("risk_class", sa.String(length=32), nullable=True),
        sa.Column("current_stage", sa.String(length=256), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_missions_status", "missions", ["status"], unique=False)
    op.create_index("ix_missions_created_by", "missions", ["created_by"], unique=False)

    op.create_table(
        "mission_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=64), nullable=True),
        sa.Column("actor_id", sa.String(length=256), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"],
            ["missions.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_mission_events_mission_id", "mission_events", ["mission_id"], unique=False
    )

    op.create_table(
        "approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action_type", sa.String(length=128), nullable=False),
        sa.Column("risk_class", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(length=256), nullable=False),
        sa.Column("requested_via", sa.String(length=64), nullable=False),
        sa.Column("decided_by", sa.String(length=256), nullable=True),
        sa.Column("decided_via", sa.String(length=64), nullable=True),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["mission_id"],
            ["missions.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_approvals_mission_id", "approvals", ["mission_id"], unique=False)
    op.create_index("ix_approvals_status", "approvals", ["status"], unique=False)

    op.create_table(
        "workers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("worker_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("auth_state", sa.String(length=64), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_table(
        "surface_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("surface_type", sa.String(length=32), nullable=False),
        sa.Column("user_identity", sa.String(length=512), nullable=True),
        sa.Column(
            "trust_level",
            sa.String(length=32),
            nullable=False,
            server_default="standard",
        ),
        sa.Column("session_state", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("receipt_type", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"],
            ["missions.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_receipts_mission_id", "receipts", ["mission_id"], unique=False)

    op.create_table(
        "cost_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("model_name", sa.String(length=256), nullable=False),
        sa.Column("token_input", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_output", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "estimated_cost_usd",
            sa.Numeric(10, 6),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["mission_id"],
            ["missions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["worker_id"],
            ["workers.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_cost_events_mission_id", "cost_events", ["mission_id"], unique=False)
    op.create_index("ix_cost_events_worker_id", "cost_events", ["worker_id"], unique=False)


def downgrade() -> None:
    op.drop_table("cost_events")
    op.drop_table("receipts")
    op.drop_table("surface_sessions")
    op.drop_table("integrations")
    op.drop_table("workers")
    op.drop_table("approvals")
    op.drop_table("mission_events")
    op.drop_table("missions")
