"""Server-Sent Events stream — canonical mission_event + mission snapshots from the same DB rows as REST."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.auth import require_api_key
from app.realtime.hub import get_hub
from app.schemas.updates import UpdatesStatus

router = APIRouter()


@router.get("", response_model=UpdatesStatus)
async def updates_status() -> UpdatesStatus:
    return UpdatesStatus()


@router.get("/stream")
async def stream_updates(_: None = Depends(require_api_key)) -> StreamingResponse:
    """SSE: each `data` line is a JSON object: `{type: mission_event|mission, ...}`."""

    async def event_generator():
        hub = get_hub()
        yield "retry: 5000\n\n"
        async for msg in hub.subscribe():
            yield f"data: {json.dumps(msg)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
