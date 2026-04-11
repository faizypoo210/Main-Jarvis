"""Twilio SMS inbound webhook for approval APPROVE/DENY/READ — no API key; signature validation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.sms_approval_service import handle_twilio_inbound

router = APIRouter()


@router.post(
    "/integrations/sms/inbound",
    summary="Twilio SMS inbound (approval commands)",
    response_class=Response,
)
async def twilio_sms_inbound(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> Response:
    """TwiML response. Commands: APPROVE <code>, DENY <code>, READ <code>."""
    xml = await handle_twilio_inbound(request, session)
    return Response(content=xml, media_type="application/xml")
