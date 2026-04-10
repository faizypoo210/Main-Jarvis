"""Updates / outbox placeholder."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.updates import UpdatesStatus

router = APIRouter()


@router.get("", response_model=UpdatesStatus)
async def updates_status() -> UpdatesStatus:
    return UpdatesStatus()
