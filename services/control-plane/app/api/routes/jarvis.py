"""Jarvis contextual reply (OpenClaw-backed with safe fallback)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.models.mission import Mission
from app.models.receipt import Receipt
from app.repositories.approval_repo import ApprovalRepository
from app.services.jarvis_reply import build_reply

router = APIRouter()


class JarvisReplyRequest(BaseModel):
    user_text: str = Field(..., min_length=1, max_length=16_000)


class JarvisReplyResponse(BaseModel):
    reply: str
    source: str


@router.post("/reply", response_model=JarvisReplyResponse)
async def post_jarvis_reply(
    body: JarvisReplyRequest,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> JarvisReplyResponse:
    stmt_m = (
        select(Mission)
        .where(~Mission.status.in_(("complete", "failed")))
        .order_by(Mission.updated_at.desc())
        .limit(40)
    )
    m_rows = await session.execute(stmt_m)
    missions = list(m_rows.scalars().all())
    active_missions = [(m.title.strip() or "(untitled)", m.status) for m in missions]

    pending = await ApprovalRepository.get_pending(session, limit=200)
    pending_count = len(pending)

    stmt_r = select(Receipt).order_by(Receipt.created_at.desc()).limit(3)
    r_rows = await session.execute(stmt_r)
    receipts = list(r_rows.scalars().all())
    recent = [rec.summary for rec in receipts]

    reply, source = await build_reply(
        body.user_text,
        active_missions,
        pending_count,
        recent,
    )
    return JarvisReplyResponse(reply=reply, source=source)
