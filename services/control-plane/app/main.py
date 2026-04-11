"""Jarvis Control Plane — authoritative mission and event API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import (
    approvals,
    commands,
    health,
    missions,
    operator,
    receipts,
    system,
    updates,
)
from app.core.config import get_settings
from app.core.db import engine
from app.core.logging import configure_logging, get_logger

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
    yield
    await engine.dispose()


app = FastAPI(title="Jarvis Control Plane", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])

api_v1_prefix = "/api/v1"
app.include_router(commands.router, prefix=f"{api_v1_prefix}/commands", tags=["commands"])
app.include_router(missions.router, prefix=f"{api_v1_prefix}/missions", tags=["missions"])
app.include_router(approvals.router, prefix=f"{api_v1_prefix}/approvals", tags=["approvals"])
app.include_router(receipts.router, prefix=f"{api_v1_prefix}/receipts", tags=["receipts"])
app.include_router(updates.router, prefix=f"{api_v1_prefix}/updates", tags=["updates"])
app.include_router(system.router, prefix=api_v1_prefix, tags=["system"])
app.include_router(operator.router, prefix=api_v1_prefix, tags=["operator"])
