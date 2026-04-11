"""Memory domain — durable operator context."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory_item import MemoryItem
from app.models.receipt import Receipt
from app.repositories.memory_repo import MemoryRepository
from app.repositories.mission_event_repo import MissionEventRepository
from app.repositories.mission_repo import MissionRepository
from app.schemas.memory import (
    MemoryCountsResponse,
    MemoryCreate,
    MemoryItemRead,
    MemoryListResponse,
    MemoryPatch,
    MissionMemoryPromote,
)
from app.services.memory_promotion import parse_receipt_memory_candidate, parse_system_memory_candidate


async def _emit_timeline_event(
    session: AsyncSession,
    *,
    mission_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> UUID:
    ev = await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type=event_type,
        actor_type="system",
        actor_id="control_plane",
        payload=payload,
    )
    return ev.id


class MemoryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._missions = MissionRepository(session)

    async def list_memory(
        self,
        *,
        memory_type: str | None,
        status: str | None,
        q: str | None,
        limit: int,
        offset: int,
    ) -> MemoryListResponse:
        total = await MemoryRepository.count_filtered(
            self._session,
            memory_type=memory_type,
            status=status,
            q=q,
        )
        rows = await MemoryRepository.list_filtered(
            self._session,
            memory_type=memory_type,
            status=status,
            q=q,
            limit=limit,
            offset=offset,
        )
        return MemoryListResponse(
            items=[MemoryItemRead.model_validate(r) for r in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get(self, memory_id: UUID) -> MemoryItemRead:
        row = await MemoryRepository.get(self._session, memory_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
        return MemoryItemRead.model_validate(row)

    async def counts(self) -> MemoryCountsResponse:
        by_type, active, archived = await MemoryRepository.count_by_type_and_status(self._session)
        return MemoryCountsResponse(by_type=by_type, active=active, archived=archived)

    async def create_manual(self, body: MemoryCreate) -> MemoryItemRead:
        if body.mission_id is not None:
            m = await self._missions.get_by_id(body.mission_id)
            if m is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")

        tags = [t[:128] for t in (body.tags or [])][:64]
        row = MemoryItem(
            memory_type=body.memory_type,
            title=body.title.strip(),
            summary=body.summary.strip() if body.summary else None,
            content=body.content.strip() if body.content else None,
            status="active",
            importance=body.importance,
            source_kind="manual",
            source_mission_id=body.mission_id,
            source_receipt_id=None,
            source_event_id=None,
            tags=tags,
            dedupe_key=body.dedupe_key.strip() if body.dedupe_key else None,
        )
        try:
            row = await MemoryRepository.create(self._session, row)
        except IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="dedupe_key already exists",
            ) from e

        if body.mission_id is not None:
            eid = await _emit_timeline_event(
                self._session,
                mission_id=body.mission_id,
                event_type="memory_saved",
                payload={
                    "memory_id": str(row.id),
                    "memory_type": row.memory_type,
                    "title": row.title,
                    "source_kind": "manual",
                },
            )
            row.source_event_id = eid
            await self._session.flush()
            await self._session.refresh(row)

        return MemoryItemRead.model_validate(row)

    async def patch(self, memory_id: UUID, body: MemoryPatch) -> MemoryItemRead:
        row = await MemoryRepository.get(self._session, memory_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")

        mission_for_event: UUID | None = row.source_mission_id
        old_status = row.status

        if body.title is not None:
            row.title = body.title.strip()
        if body.summary is not None:
            row.summary = body.summary.strip() if body.summary else None
        if body.content is not None:
            row.content = body.content.strip() if body.content else None
        if body.status is not None:
            row.status = body.status
        if body.importance is not None:
            row.importance = body.importance
        if body.tags is not None:
            row.tags = [t[:128] for t in body.tags][:64]
        if body.last_reviewed_at is not None:
            row.last_reviewed_at = body.last_reviewed_at
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(row)

        if mission_for_event is not None and body.status == "archived" and old_status != "archived":
            await _emit_timeline_event(
                self._session,
                mission_id=mission_for_event,
                event_type="memory_archived",
                payload={
                    "memory_id": str(row.id),
                    "memory_type": row.memory_type,
                    "title": row.title,
                    "source_kind": row.source_kind,
                },
            )

        return MemoryItemRead.model_validate(row)

    async def promote_from_mission(self, body: MissionMemoryPromote) -> MemoryItemRead:
        m = await self._missions.get_by_id(body.mission_id)
        if m is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")

        tags = [t[:128] for t in (body.tags or [])][:64]
        row = MemoryItem(
            memory_type=body.memory_type,
            title=body.title.strip(),
            summary=body.summary.strip() if body.summary else None,
            content=body.content.strip() if body.content else None,
            status="active",
            importance=body.importance,
            source_kind="mission_promotion",
            source_mission_id=body.mission_id,
            source_receipt_id=None,
            source_event_id=None,
            tags=tags,
            dedupe_key=body.dedupe_key.strip() if body.dedupe_key else None,
        )
        try:
            row = await MemoryRepository.create(self._session, row)
        except IntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="dedupe_key already exists",
            ) from e

        eid = await _emit_timeline_event(
            self._session,
            mission_id=body.mission_id,
            event_type="memory_promoted",
            payload={
                "memory_id": str(row.id),
                "memory_type": row.memory_type,
                "title": row.title,
                "source_kind": "mission_promotion",
            },
        )
        row.source_event_id = eid
        await self._session.flush()
        await self._session.refresh(row)
        return MemoryItemRead.model_validate(row)


async def try_promote_from_receipt(
    session: AsyncSession,
    receipt: Receipt,
    mission_id: UUID,
) -> None:
    """If receipt payload contains a valid structured candidate, persist one memory row."""
    payload = receipt.payload if isinstance(receipt.payload, dict) else {}
    cand = parse_receipt_memory_candidate(payload) or parse_system_memory_candidate(payload)
    if cand is None:
        return

    mrepo = MissionRepository(session)
    m = await mrepo.get_by_id(mission_id)
    if m is None:
        return

    row = MemoryItem(
        memory_type=cand["memory_type"],
        title=cand["title"],
        summary=cand.get("summary"),
        content=cand.get("content"),
        status="active",
        importance=3,
        source_kind="receipt_promotion",
        source_mission_id=mission_id,
        source_receipt_id=receipt.id,
        source_event_id=None,
        tags=cand.get("tags") or [],
        dedupe_key=cand.get("dedupe_key"),
    )
    try:
        row = await MemoryRepository.create(session, row)
    except IntegrityError:
        # Idempotent promotion
        return

    eid = await _emit_timeline_event(
        session,
        mission_id=mission_id,
        event_type="memory_promoted",
        payload={
            "memory_id": str(row.id),
            "memory_type": row.memory_type,
            "title": row.title,
            "source_kind": "receipt_promotion",
            "source_receipt_id": str(receipt.id),
        },
    )
    row.source_event_id = eid
    await session.flush()
