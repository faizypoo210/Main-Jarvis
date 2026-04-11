"""Memory items — durable operator context (v1).

Revision ID: 003_memory_items
Revises: 002_approval_cmd
Create Date: 2026-04-11

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003_memory_items"
down_revision: Union[str, None] = "002_approval_cmd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "memory_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "importance",
            sa.Integer(),
            nullable=False,
            server_default="3",
        ),
        sa.Column("source_kind", sa.String(length=64), nullable=False),
        sa.Column("source_mission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_receipt_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("dedupe_key", sa.String(length=256), nullable=True),
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
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_mission_id"],
            ["missions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_receipt_id"],
            ["receipts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_event_id"],
            ["mission_events.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_items_memory_type", "memory_items", ["memory_type"])
    op.create_index("ix_memory_items_status", "memory_items", ["status"])
    op.create_index("ix_memory_items_source_kind", "memory_items", ["source_kind"])
    op.create_index("ix_memory_items_source_mission_id", "memory_items", ["source_mission_id"])
    op.create_index("ix_memory_items_source_receipt_id", "memory_items", ["source_receipt_id"])
    op.create_index("ix_memory_items_dedupe_key", "memory_items", ["dedupe_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_memory_items_dedupe_key", table_name="memory_items")
    op.drop_index("ix_memory_items_source_receipt_id", table_name="memory_items")
    op.drop_index("ix_memory_items_source_mission_id", table_name="memory_items")
    op.drop_index("ix_memory_items_source_kind", table_name="memory_items")
    op.drop_index("ix_memory_items_status", table_name="memory_items")
    op.drop_index("ix_memory_items_memory_type", table_name="memory_items")
    op.drop_table("memory_items")
