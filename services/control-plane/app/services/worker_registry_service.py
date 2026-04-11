"""Worker register + heartbeat (idempotent upsert by worker_type + instance_id)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.worker import Worker
from app.repositories.worker_repo import WorkerRepository
from app.schemas.workers import (
    OperatorWorkersResponse,
    WorkerHeartbeatRequest,
    WorkerRead,
    WorkerRegisterRequest,
    WorkerRegistrySummary,
)


def _now() -> datetime:
    return datetime.now(UTC)


async def register_worker(
    session: AsyncSession, body: WorkerRegisterRequest
) -> WorkerRead:
    now = _now()
    existing = await WorkerRepository.get_by_type_instance(
        session, worker_type=body.worker_type, instance_id=body.instance_id
    )
    meta = _safe_meta(body.meta)
    if existing is None:
        row = Worker(
            id=uuid.uuid4(),
            worker_type=body.worker_type,
            instance_id=body.instance_id,
            name=body.name,
            status=body.status,
            host=body.host,
            version=body.version,
            last_heartbeat_at=now,
            started_at=now,
            last_error=None,
            updated_at=now,
            metadata_=meta if meta else None,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return WorkerRead.model_validate(row)

    existing.name = body.name
    existing.status = body.status
    existing.host = body.host
    existing.version = body.version
    existing.last_heartbeat_at = now
    existing.updated_at = now
    if existing.started_at is None:
        existing.started_at = now
    if meta:
        existing.metadata_ = {**(existing.metadata_ or {}), **meta}
    await session.flush()
    await session.refresh(existing)
    return WorkerRead.model_validate(existing)


async def heartbeat_worker(
    session: AsyncSession, body: WorkerHeartbeatRequest
) -> WorkerRead:
    now = _now()
    existing = await WorkerRepository.get_by_type_instance(
        session, worker_type=body.worker_type, instance_id=body.instance_id
    )
    meta = _safe_meta(body.meta)
    err = _truncate(body.last_error, 2048) if body.last_error else None

    if existing is None:
        row = Worker(
            id=uuid.uuid4(),
            worker_type=body.worker_type,
            instance_id=body.instance_id,
            name=f"{body.worker_type} ({body.instance_id})",
            status=body.status,
            host=None,
            version=None,
            last_heartbeat_at=now,
            started_at=now,
            last_error=err,
            updated_at=now,
            metadata_=meta if meta else None,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return WorkerRead.model_validate(row)

    existing.status = body.status
    existing.last_heartbeat_at = now
    existing.updated_at = now
    existing.last_error = err
    if meta:
        existing.metadata_ = {**(existing.metadata_ or {}), **meta}
    await session.flush()
    await session.refresh(existing)
    return WorkerRead.model_validate(existing)


def _safe_meta(meta: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in (meta or {}).items():
        ks = str(k)[:128]
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[ks] = v if not isinstance(v, str) else v[:4000]
        elif isinstance(v, list) and len(v) <= 32:
            out[ks] = [str(x)[:500] for x in v[:32]]
    return out


def _truncate(s: str, n: int) -> str:
    t = s.strip()
    return t if len(t) <= n else t[: n - 1] + "…"


async def list_operator_workers(
    session: AsyncSession, *, stale_threshold_minutes: float
) -> OperatorWorkersResponse:
    rows = await WorkerRepository.list_all(session)
    return OperatorWorkersResponse(
        generated_at=_now().isoformat().replace("+00:00", "Z"),
        workers=[WorkerRead.model_validate(r) for r in rows],
        stale_threshold_minutes=stale_threshold_minutes,
    )


async def build_registry_summary(
    session: AsyncSession, *, threshold_minutes: float
) -> WorkerRegistrySummary:
    rows = await WorkerRepository.list_all(session)
    now = _now()
    cutoff = now.timestamp() - threshold_minutes * 60.0
    healthy = 0
    stale = 0
    for r in rows:
        lb = r.last_heartbeat_at
        if lb is None:
            stale += 1
            continue
        if lb.tzinfo is None:
            lb = lb.replace(tzinfo=UTC)
        if lb.timestamp() >= cutoff:
            healthy += 1
        else:
            stale += 1
    return WorkerRegistrySummary(
        registered_total=len(rows),
        healthy_heartbeat=healthy,
        stale_or_absent=stale,
        threshold_minutes=threshold_minutes,
    )
