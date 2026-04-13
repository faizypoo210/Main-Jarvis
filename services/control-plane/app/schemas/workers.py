"""Worker registry + heartbeat (v1) — no secrets in payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

WorkerType = Literal[
    "coordinator",
    "executor",
    "voice",
    "heartbeat",
    "control_plane",
]

WorkerStatus = Literal[
    "starting",
    "healthy",
    "degraded",
    "offline",
    "stopped",
    "unknown",
]


ALLOWED_WORKER_TYPES = frozenset(
    {"coordinator", "executor", "voice", "heartbeat", "control_plane"}
)


class WorkerRegisterRequest(BaseModel):
    worker_type: str = Field(..., min_length=1, max_length=64)
    instance_id: str = Field(default="default", max_length=128)
    name: str = Field(..., min_length=1, max_length=256)
    status: str = Field(default="healthy", max_length=32)
    host: str | None = Field(None, max_length=256)
    version: str | None = Field(None, max_length=128)
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("worker_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        t = str(v).strip().lower()
        if t not in ALLOWED_WORKER_TYPES:
            raise ValueError(f"worker_type must be one of: {sorted(ALLOWED_WORKER_TYPES)}")
        return t


class WorkerHeartbeatRequest(BaseModel):
    worker_type: str = Field(..., min_length=1, max_length=64)
    instance_id: str = Field(default="default", max_length=128)
    status: str = Field(default="healthy", max_length=32)
    meta: dict[str, Any] = Field(default_factory=dict)
    last_error: str | None = Field(None, max_length=2048)

    @field_validator("worker_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        t = str(v).strip().lower()
        if t not in ALLOWED_WORKER_TYPES:
            raise ValueError(f"worker_type must be one of: {sorted(ALLOWED_WORKER_TYPES)}")
        return t


class WorkerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    worker_type: str
    instance_id: str
    name: str
    status: str
    host: str | None = None
    version: str | None = None
    last_heartbeat_at: datetime | None = None
    started_at: datetime | None = None
    last_error: str | None = None
    updated_at: datetime
    meta: dict[str, Any] | None = Field(
        default=None,
        validation_alias="metadata_",
        serialization_alias="meta",
    )


class OperatorWorkersResponse(BaseModel):
    generated_at: str
    workers: list[WorkerRead]
    stale_threshold_minutes: float


class WorkerRegistrySummary(BaseModel):
    """Compact snapshot for system health (direct DB truth)."""

    registered_total: int = 0
    healthy_heartbeat: int = 0
    stale_or_absent: int = 0
    threshold_minutes: float = 15.0
    # Rows whose latest metadata reports ready_state (from worker process).
    readiness_ready: int = 0
    readiness_not_ready: int = 0
    readiness_degraded: int = 0
