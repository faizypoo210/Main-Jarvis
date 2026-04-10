"""Health check."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "jarvis-control-plane",
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
