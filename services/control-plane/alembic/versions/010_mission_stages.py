"""Add nullable JSONB ``stages`` column to ``missions``."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "010_mission_stages"
down_revision = "009_operator_inbox_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "missions",
        sa.Column("stages", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("missions", "stages")
