"""Cost events v1: direct spend truth (source_kind, receipt link, cost_status, tokens, no fake amounts)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "006_cost_events_v1"
down_revision = "005_worker_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cost_events", sa.Column("source_kind", sa.String(length=32), nullable=True))
    op.add_column(
        "cost_events",
        sa.Column("source_receipt_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("cost_events", sa.Column("provider", sa.String(length=64), nullable=True))
    op.add_column("cost_events", sa.Column("operation", sa.String(length=256), nullable=True))
    op.add_column("cost_events", sa.Column("amount", sa.Numeric(precision=18, scale=6), nullable=True))
    op.add_column("cost_events", sa.Column("currency", sa.String(length=8), nullable=True))
    op.add_column("cost_events", sa.Column("cost_status", sa.String(length=32), nullable=True))
    op.add_column("cost_events", sa.Column("usage_tokens_input", sa.Integer(), nullable=True))
    op.add_column("cost_events", sa.Column("usage_tokens_output", sa.Integer(), nullable=True))
    op.add_column(
        "cost_events",
        sa.Column("usage_units", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("cost_events", sa.Column("notes", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE cost_events SET
          source_kind = 'execution',
          provider = 'legacy',
          operation = LEFT(COALESCE(model_name, 'unknown'), 256),
          amount = CASE
            WHEN estimated_cost_usd IS NOT NULL AND estimated_cost_usd > 0 THEN estimated_cost_usd
            ELSE NULL
          END,
          currency = CASE
            WHEN estimated_cost_usd IS NOT NULL AND estimated_cost_usd > 0 THEN 'USD'
            ELSE NULL
          END,
          cost_status = CASE
            WHEN estimated_cost_usd IS NOT NULL AND estimated_cost_usd > 0 THEN 'estimated'
            ELSE 'unknown'
          END,
          usage_tokens_input = token_input,
          usage_tokens_output = token_output,
          notes = 'Migrated from pre-v1 cost_events schema.'
        """
    )

    op.execute(
        """
        UPDATE cost_events SET source_kind = 'execution', cost_status = 'unknown'
        WHERE source_kind IS NULL OR cost_status IS NULL
        """
    )

    op.alter_column("cost_events", "source_kind", nullable=False)
    op.alter_column("cost_events", "cost_status", nullable=False)

    op.drop_constraint("cost_events_worker_id_fkey", "cost_events", type_="foreignkey")
    op.drop_index("ix_cost_events_worker_id", table_name="cost_events")
    op.drop_column("cost_events", "worker_id")
    op.drop_column("cost_events", "model_name")
    op.drop_column("cost_events", "token_input")
    op.drop_column("cost_events", "token_output")
    op.drop_column("cost_events", "estimated_cost_usd")

    op.create_foreign_key(
        "cost_events_source_receipt_id_fkey",
        "cost_events",
        "receipts",
        ["source_receipt_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_cost_events_source_receipt_id",
        "cost_events",
        ["source_receipt_id"],
        unique=False,
    )
    op.create_index("ix_cost_events_cost_status", "cost_events", ["cost_status"], unique=False)
    op.create_index("ix_cost_events_provider", "cost_events", ["provider"], unique=False)
    op.execute(
        """
        CREATE UNIQUE INDEX uq_cost_events_source_receipt_id
        ON cost_events (source_receipt_id)
        WHERE source_receipt_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_cost_events_source_receipt_id")
    op.drop_index("ix_cost_events_provider", table_name="cost_events")
    op.drop_index("ix_cost_events_cost_status", table_name="cost_events")
    op.drop_index("ix_cost_events_source_receipt_id", table_name="cost_events")
    op.drop_constraint("cost_events_source_receipt_id_fkey", "cost_events", type_="foreignkey")

    op.add_column(
        "cost_events",
        sa.Column("estimated_cost_usd", sa.Numeric(precision=10, scale=6), nullable=True),
    )
    op.add_column("cost_events", sa.Column("token_output", sa.Integer(), nullable=True))
    op.add_column("cost_events", sa.Column("token_input", sa.Integer(), nullable=True))
    op.add_column("cost_events", sa.Column("model_name", sa.String(length=256), nullable=True))
    op.add_column(
        "cost_events",
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.execute(
        """
        UPDATE cost_events SET
          estimated_cost_usd = COALESCE(amount, 0),
          token_input = COALESCE(usage_tokens_input, 0),
          token_output = COALESCE(usage_tokens_output, 0),
          model_name = COALESCE(LEFT(operation, 256), 'unknown')
        """
    )
    op.execute(
        """
        UPDATE cost_events SET
          estimated_cost_usd = 0,
          token_input = 0,
          token_output = 0,
          model_name = 'unknown'
        WHERE estimated_cost_usd IS NULL
        """
    )

    op.alter_column("cost_events", "model_name", nullable=False)
    op.alter_column("cost_events", "token_input", nullable=False, server_default="0")
    op.alter_column("cost_events", "token_output", nullable=False, server_default="0")
    op.alter_column(
        "cost_events",
        "estimated_cost_usd",
        nullable=False,
        server_default="0",
    )

    op.drop_column("cost_events", "notes")
    op.drop_column("cost_events", "usage_units")
    op.drop_column("cost_events", "usage_tokens_output")
    op.drop_column("cost_events", "usage_tokens_input")
    op.drop_column("cost_events", "currency")
    op.drop_column("cost_events", "amount")
    op.drop_column("cost_events", "operation")
    op.drop_column("cost_events", "provider")
    op.drop_column("cost_events", "source_receipt_id")
    op.drop_column("cost_events", "source_kind")
    op.drop_column("cost_events", "cost_status")

    op.create_foreign_key(
        "cost_events_worker_id_fkey",
        "cost_events",
        "workers",
        ["worker_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_cost_events_worker_id", "cost_events", ["worker_id"], unique=False)
