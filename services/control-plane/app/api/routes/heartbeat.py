"""Heartbeat supervision — run cycle + operator snapshot."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.core.logging import get_logger
from app.core.schema_guard import OPERATOR_SCHEMA_REPAIR_HINT, is_schema_drift_db_error
from app.schemas.heartbeat import HeartbeatOperatorResponse, HeartbeatRunResponse
from app.services.heartbeat_service import build_operator_snapshot, run_heartbeat_cycle

router = APIRouter()
log = get_logger(__name__)


@router.get("/operator/heartbeat", response_model=HeartbeatOperatorResponse)
async def operator_heartbeat(
    session: AsyncSession = Depends(get_db),
) -> HeartbeatOperatorResponse:
    """Open heartbeat findings and counts (quiet when nothing is open)."""
    try:
        return await build_operator_snapshot(session)
    except Exception as e:
        if is_schema_drift_db_error(e):
            log.exception("operator_heartbeat_schema_drift")
            now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            return HeartbeatOperatorResponse(
                generated_at=now,
                open_count=0,
                by_severity={},
                by_type={},
                open_findings=[],
                operator_note=OPERATOR_SCHEMA_REPAIR_HINT[:500],
            )
        raise


@router.post("/heartbeat/run", response_model=HeartbeatRunResponse)
async def heartbeat_run(
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> HeartbeatRunResponse:
    """Evaluate supervision rules and sync findings (heartbeat worker)."""
    try:
        return await run_heartbeat_cycle(session)
    except Exception as e:
        if is_schema_drift_db_error(e):
            log.exception("heartbeat_run_schema_drift")
            raise HTTPException(status_code=503, detail=OPERATOR_SCHEMA_REPAIR_HINT) from e
        raise
