"""Add command_text and dashclaw_decision_id to approvals.

Revision ID: 002_approval_cmd
Revises: 001_initial
Create Date: 2026-04-07

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_approval_cmd"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "approvals",
        sa.Column("command_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "approvals",
        sa.Column("dashclaw_decision_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("approvals", "dashclaw_decision_id")
    op.drop_column("approvals", "command_text")
