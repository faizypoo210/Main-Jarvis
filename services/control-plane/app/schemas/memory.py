"""Operator memory API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


MEMORY_TYPES = frozenset(
    {
        "operator",
        "project",
        "person",
        "system",
        "preference",
        "integration",
        "workflow",
    }
)


class MemoryItemRead(BaseModel):
    id: UUID
    memory_type: str
    title: str
    summary: str | None
    content: str | None
    status: str
    importance: int
    source_kind: str
    source_mission_id: UUID | None = None
    source_receipt_id: UUID | None = None
    source_event_id: UUID | None = None
    tags: list[str]
    dedupe_key: str | None = None
    created_at: datetime
    updated_at: datetime
    last_reviewed_at: datetime | None = None

    model_config = {"from_attributes": True}


class MemoryListResponse(BaseModel):
    items: list[MemoryItemRead]
    total: int
    limit: int
    offset: int


class MemoryCountsResponse(BaseModel):
    by_type: dict[str, int]
    active: int
    archived: int


class MemoryCreate(BaseModel):
    """Manual operator-authored memory (conservative; not a log import)."""

    memory_type: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=512)
    summary: str | None = Field(None, max_length=8000)
    content: str | None = Field(None, max_length=64000)
    importance: int = Field(3, ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    mission_id: UUID | None = Field(
        default=None,
        description="If set, a mission timeline event is recorded on this mission.",
    )
    dedupe_key: str | None = Field(None, max_length=256)

    @field_validator("memory_type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        s = v.strip()
        if s not in MEMORY_TYPES:
            raise ValueError(f"memory_type must be one of: {sorted(MEMORY_TYPES)}")
        return s


class MemoryPatch(BaseModel):
    """Archive or light edits — not bulk import."""

    title: str | None = Field(None, min_length=1, max_length=512)
    summary: str | None = Field(None, max_length=8000)
    content: str | None = Field(None, max_length=64000)
    status: str | None = Field(None, pattern="^(active|archived)$")
    importance: int | None = Field(None, ge=1, le=5)
    tags: list[str] | None = None
    last_reviewed_at: datetime | None = None


class MissionMemoryPromote(BaseModel):
    """Explicit promotion from a completed or active mission context (operator-initiated)."""

    mission_id: UUID
    memory_type: str = Field(..., min_length=1, max_length=64)
    title: str = Field(..., min_length=1, max_length=512)
    summary: str | None = Field(None, max_length=8000)
    content: str | None = Field(None, max_length=64000)
    importance: int = Field(3, ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    dedupe_key: str | None = Field(None, max_length=256)

    @field_validator("memory_type")
    @classmethod
    def _type_ok(cls, v: str) -> str:
        s = v.strip()
        if s not in MEMORY_TYPES:
            raise ValueError(f"memory_type must be one of: {sorted(MEMORY_TYPES)}")
        return s
