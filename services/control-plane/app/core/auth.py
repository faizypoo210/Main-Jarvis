"""Control plane mutation auth — server-side only (no browser-bundled secrets)."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import ControlPlaneAuthMode, Settings, get_settings


def assert_auth_config_for_startup(settings: Settings, *, testing: bool) -> None:
    """Fail fast when production config would leave mutations effectively open by accident.

    When ``testing`` is True (pytest), validation is skipped so tests can vary auth per case.
    """
    if testing:
        return
    if settings.CONTROL_PLANE_AUTH_MODE == ControlPlaneAuthMode.API_KEY:
        if not (settings.CONTROL_PLANE_API_KEY or "").strip():
            raise RuntimeError(
                "CONTROL_PLANE_AUTH_MODE=api_key requires a non-empty CONTROL_PLANE_API_KEY. "
                "For explicit insecure local-only use, set CONTROL_PLANE_AUTH_MODE=local_trusted "
                "(see .env.example)."
            )


async def require_api_key(
    x_api_key: str | None = Header(None, alias="x-api-key"),
) -> None:
    """Require a valid API key for mutation routes, unless in local_trusted mode (explicit opt-in)."""
    settings = get_settings()
    if settings.CONTROL_PLANE_AUTH_MODE == ControlPlaneAuthMode.LOCAL_TRUSTED:
        return
    key = (settings.CONTROL_PLANE_API_KEY or "").strip()
    if not key:
        # Should not happen if startup validation ran; defensive.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: api_key mode without CONTROL_PLANE_API_KEY",
        )
    if (x_api_key or "").strip() != key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
