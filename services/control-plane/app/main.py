"""Jarvis Control Plane — authoritative mission and event API."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import (
    approvals,
    commands,
    intake,
    github_integration,
    gmail_integration,
    health,
    heartbeat,
    jarvis,
    missions,
    operator,
    operator_memory,
    receipts,
    sms_integration,
    system,
    updates,
    workers,
)
from app.core.auth import assert_auth_config_for_startup
from app.core.config import ControlPlaneAuthMode, get_settings
from app.core.db import engine
from app.core.logging import configure_logging, get_logger
from app.core.schema_guard import verify_schema_at_startup

configure_logging()
log = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    log.info(
        "database connectivity verified service=%s",
        settings.SERVICE_NAME,
    )
    await verify_schema_at_startup(engine)
    testing = os.environ.get("CONTROL_PLANE_TESTING") == "1"
    assert_auth_config_for_startup(get_settings(), testing=testing)
    if not testing and settings.CONTROL_PLANE_AUTH_MODE == ControlPlaneAuthMode.LOCAL_TRUSTED:
        log.warning(
            "SECURITY: CONTROL_PLANE_AUTH_MODE=local_trusted — API key is not enforced for mutations; "
            "use only on trusted localhost networks."
        )
    yield
    # Pytest drives repeated ASGI lifespans in-process; disposing the global engine
    # breaks later tests. Production (uvicorn) still shuts down cleanly without this flag.
    if os.environ.get("CONTROL_PLANE_TESTING") != "1":
        await engine.dispose()


def create_app() -> FastAPI:
    """Application factory — used by uvicorn and by the pytest ASGI client."""
    application = FastAPI(title="Jarvis Control Plane", lifespan=lifespan)
    _register_routes(application)
    return application


def _register_routes(application: FastAPI) -> None:
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router, tags=["health"])

    api_v1_prefix = "/api/v1"
    application.include_router(commands.router, prefix=f"{api_v1_prefix}/commands", tags=["commands"])
    application.include_router(intake.router, prefix=f"{api_v1_prefix}/intake", tags=["intake"])
    application.include_router(missions.router, prefix=f"{api_v1_prefix}/missions", tags=["missions"])
    application.include_router(
        github_integration.router,
        prefix=f"{api_v1_prefix}/missions",
        tags=["integrations-github"],
    )
    application.include_router(
        gmail_integration.router,
        prefix=f"{api_v1_prefix}/missions",
        tags=["integrations-gmail"],
    )
    application.include_router(approvals.router, prefix=f"{api_v1_prefix}/approvals", tags=["approvals"])
    application.include_router(receipts.router, prefix=f"{api_v1_prefix}/receipts", tags=["receipts"])
    application.include_router(jarvis.router, prefix=f"{api_v1_prefix}/jarvis", tags=["jarvis"])
    application.include_router(updates.router, prefix=f"{api_v1_prefix}/updates", tags=["updates"])
    application.include_router(workers.router, prefix=api_v1_prefix, tags=["workers"])
    application.include_router(system.router, prefix=api_v1_prefix, tags=["system"])
    application.include_router(operator.router, prefix=api_v1_prefix, tags=["operator"])
    application.include_router(operator_memory.router, prefix=api_v1_prefix, tags=["operator-memory"])
    application.include_router(heartbeat.router, prefix=api_v1_prefix, tags=["heartbeat"])
    application.include_router(sms_integration.router, prefix=api_v1_prefix, tags=["integrations-sms"])


app = create_app()
