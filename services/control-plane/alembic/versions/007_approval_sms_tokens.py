"""SMS approval tokens v1 — short codes for approve/deny/read via inbound SMS (Twilio)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "007_approval_sms_tokens"
down_revision = "006_cost_events_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approval_sms_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approval_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sms_code", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("phone_hint", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outbound_note", sa.Text(), nullable=True),
        sa.Column("inbound_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_id", name="uq_approval_sms_tokens_approval_id"),
        sa.UniqueConstraint("sms_code", name="uq_approval_sms_tokens_sms_code"),
    )


def downgrade() -> None:
    op.drop_table("approval_sms_tokens")
