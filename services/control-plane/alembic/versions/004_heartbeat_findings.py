"""Heartbeat findings — proactive supervision (v1).

Revision ID: 004_heartbeat_findings
Revises: 003_memory_items
Create Date: 2026-04-11

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_heartbeat_findings"
down_revision: Union[str, None] = "003_memory_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "heartbeat_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=512), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("integration_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("service_component", sa.String(length=64), nullable=True),
        sa.Column("provenance_note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["mission_id"], ["missions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["integration_id"], ["integrations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_heartbeat_findings_dedupe_key"),
    )
    op.create_index("ix_heartbeat_findings_status", "heartbeat_findings", ["status"])
    op.create_index("ix_heartbeat_findings_finding_type", "heartbeat_findings", ["finding_type"])
    op.create_index("ix_heartbeat_findings_last_seen_at", "heartbeat_findings", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_heartbeat_findings_last_seen_at", table_name="heartbeat_findings")
    op.drop_index("ix_heartbeat_findings_finding_type", table_name="heartbeat_findings")
    op.drop_index("ix_heartbeat_findings_status", table_name="heartbeat_findings")
    op.drop_table("heartbeat_findings")
