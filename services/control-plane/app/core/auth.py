"""API key authentication for mutation routes."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_api_key(
    x_api_key: str | None = Header(None, alias="x-api-key"),
) -> None:
    settings = get_settings()
    if not settings.CONTROL_PLANE_API_KEY:
        return  # auth disabled if key not configured
    if x_api_key != settings.CONTROL_PLANE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
