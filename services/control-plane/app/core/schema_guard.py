"""Detect Postgres schema drift vs Alembic head and critical tables/columns.

Fails fast at startup (unless CONTROL_PLANE_TESTING=1 or CONTROL_PLANE_SKIP_SCHEMA_CHECK=1).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger

log = get_logger(__name__)

OPERATOR_SCHEMA_REPAIR_HINT = (
    "Database schema is behind Alembic head or missing required objects. "
    "From services/control-plane with DATABASE_URL set: python -m alembic upgrade head"
)


def control_plane_root() -> Path:
    """services/control-plane (parent of app/)."""
    return Path(__file__).resolve().parents[2]


def _alembic_script() -> ScriptDirectory:
    root = control_plane_root()
    ini = root / "alembic.ini"
    cfg = Config(str(ini))
    return ScriptDirectory.from_config(cfg)


def expected_alembic_head() -> str:
    """Single revision id at Alembic head (linear chain)."""
    script = _alembic_script()
    return script.get_current_head()


def is_schema_drift_db_error(exc: BaseException) -> bool:
    """Heuristic: asyncpg / SQLAlchemy errors from missing columns or tables."""
    chain: list[str] = []
    cur: BaseException | None = exc
    while cur is not None:
        chain.append(str(cur).lower())
        cur = cur.__cause__ or cur.__context__  # type: ignore[assignment]
    blob = " ".join(chain)
    if re.search(r"undefinedcolumn|undefinedtable|does not exist", blob):
        return True
    if "relation" in blob and "does not exist" in blob:
        return True
    if "column" in blob and "does not exist" in blob:
        return True
    return False


async def _current_db_revision(conn) -> str | None:
    r = await conn.execute(text("SELECT version_num FROM alembic_version"))
    rows = r.fetchall()
    if len(rows) == 0:
        return None
    if len(rows) > 1:
        revs = [str(x[0]) for x in rows]
        raise RuntimeError(
            f"{OPERATOR_SCHEMA_REPAIR_HINT} (multiple alembic_version rows: {revs})."
        )
    return str(rows[0][0])


async def _critical_schema_checks(conn) -> list[str]:
    """Return human-readable problems if critical objects are missing."""
    problems: list[str] = []
    r1 = await conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'workers' AND column_name = 'instance_id'
            """
        )
    )
    if r1.first() is None:
        problems.append("public.workers.instance_id column missing")
    r2 = await conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'heartbeat_findings'
            """
        )
    )
    if r2.first() is None:
        problems.append("public.heartbeat_findings table missing")
    return problems


async def verify_schema_at_startup(engine: AsyncEngine) -> None:
    """Raise RuntimeError with repair hint if DB is not at head or critical DDL is missing."""
    if os.environ.get("CONTROL_PLANE_TESTING") == "1":
        log.info("schema_guard_skipped reason=CONTROL_PLANE_TESTING")
        return
    if os.environ.get("CONTROL_PLANE_SKIP_SCHEMA_CHECK", "").strip() == "1":
        log.warning("schema_guard_skipped reason=CONTROL_PLANE_SKIP_SCHEMA_CHECK")
        return

    head = expected_alembic_head()
    async with engine.connect() as conn:
        try:
            db_rev = await _current_db_revision(conn)
        except Exception as e:
            if is_schema_drift_db_error(e):
                raise RuntimeError(
                    f"{OPERATOR_SCHEMA_REPAIR_HINT} (cannot read alembic_version: {e})"
                ) from e
            raise
        if db_rev is None:
            raise RuntimeError(
                f"{OPERATOR_SCHEMA_REPAIR_HINT} (alembic_version is empty; expected head {head})."
            )
        if db_rev != head:
            raise RuntimeError(
                f"{OPERATOR_SCHEMA_REPAIR_HINT} "
                f"(database at revision {db_rev!r}, Alembic head is {head!r})."
            )
        critical = await _critical_schema_checks(conn)
        if critical:
            raise RuntimeError(
                f"{OPERATOR_SCHEMA_REPAIR_HINT} (checks failed: {'; '.join(critical)})."
            )

    log.info("schema_guard_ok head=%s", head)
