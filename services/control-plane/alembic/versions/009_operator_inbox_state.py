"""Operator inbox v1 — lightweight ack/snooze state keyed by stable item_key."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "009_operator_inbox_state"
down_revision = "008_approval_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operator_inbox_state",
        sa.Column("item_key", sa.String(length=512), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("item_key"),
    )


def downgrade() -> None:
    op.drop_table("operator_inbox_state")
