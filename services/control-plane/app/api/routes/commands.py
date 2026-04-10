"""Command intake."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.schemas.commands import CommandCreate, CommandResponse
from app.services.command_service import CommandService

router = APIRouter()


@router.post("", response_model=CommandResponse)
async def create_command(
    body: CommandCreate,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> CommandResponse:
    svc = CommandService(session)
    return await svc.intake(body)
