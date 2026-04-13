"""Command intake schemas.

TRUTH_SOURCE: POST /api/v1/commands body and response; rehearsal scripts may set context.* for Redis isolation.

``POST /api/v1/commands`` is the **low-level** mission factory. Unified interpretation and
reply shaping live under ``POST /api/v1/intake`` (see ``app/schemas/intake.py``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CommandCreate(BaseModel):
    text: str = Field(..., min_length=1, description="Raw command text")
    source: str = Field(
        ...,
        pattern="^(voice|command_center|sms|api)$",
        description="Surface / origin",
    )
    surface_session_id: UUID | None = None
    context: dict[str, Any] | None = None


class CommandResponse(BaseModel):
    mission_id: UUID
    mission_status: str
    message: str
