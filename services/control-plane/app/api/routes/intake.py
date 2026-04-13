"""Unified intake — interpretation plus governed outcomes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.schemas.intake import IntakeRequest, IntakeResponse
from app.services.intake_service import IntakeService

router = APIRouter()


@router.post("", response_model=IntakeResponse)
async def intake(
    body: IntakeRequest,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> IntakeResponse:
    """Interpret natural language and route to missions, approvals, inbox, or reply-only paths."""
    svc = IntakeService(session)
    return await svc.process(body)
