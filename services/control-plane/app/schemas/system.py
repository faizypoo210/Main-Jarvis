"""Compact system health response for operator UI (no secrets, no verbose dumps)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.workers import WorkerRegistrySummary

HealthState = Literal["healthy", "degraded", "offline", "unknown"]


class ComponentHealth(BaseModel):
    status: HealthState
    detail: str | None = Field(
        default=None,
        description="Non-sensitive hint (e.g. probe URL, error class).",
    )
    probe_source: str | None = Field(
        default=None,
        description=(
            "Where this status came from: control_plane_local | configured_remote | "
            "worker_registry_inference | unknown (execution-plane components only)."
        ),
    )


class SystemHealthResponse(BaseModel):
    checked_at: str = Field(..., description="ISO-8601 UTC when this snapshot was taken.")
    control_plane: ComponentHealth
    postgres: ComponentHealth
    redis: ComponentHealth
    openclaw_gateway: ComponentHealth
    ollama: ComponentHealth
    worker_registry: WorkerRegistrySummary = Field(
        default_factory=WorkerRegistrySummary,
        description="Worker registry heartbeats (direct DB truth).",
    )
