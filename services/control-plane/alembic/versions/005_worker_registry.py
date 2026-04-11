"""Worker registry columns + unique (worker_type, instance_id)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "005_worker_registry"
down_revision = "004_heartbeat_findings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workers",
        sa.Column("instance_id", sa.String(length=128), server_default="default", nullable=False),
    )
    op.add_column("workers", sa.Column("host", sa.String(length=256), nullable=True))
    op.add_column("workers", sa.Column("version", sa.String(length=128), nullable=True))
    op.add_column(
        "workers",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("workers", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column(
        "workers",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.alter_column("workers", "instance_id", server_default=None)
    op.execute(sa.text("UPDATE workers SET instance_id = CAST(id AS TEXT)"))
    op.create_unique_constraint(
        "uq_workers_worker_type_instance_id",
        "workers",
        ["worker_type", "instance_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_workers_worker_type_instance_id", "workers", type_="unique")
    op.drop_column("workers", "updated_at")
    op.drop_column("workers", "last_error")
    op.drop_column("workers", "started_at")
    op.drop_column("workers", "version")
    op.drop_column("workers", "host")
    op.drop_column("workers", "instance_id")
