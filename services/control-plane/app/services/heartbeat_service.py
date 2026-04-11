"""Heartbeat v1 — explicit supervision checks, deduped findings.

Cost guardrails (v1): `cost_guardrail_service` evaluates `cost_events` against env thresholds; finding_types `cost_*`.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import urllib.error
import urllib.request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import engine
from app.models.heartbeat_finding import HeartbeatFinding
from app.services.approval_reminder_service import run_approval_reminder_cycle
from app.services.cost_guardrail_service import collect_cost_guardrail_candidates
from app.repositories.heartbeat_finding_repo import HeartbeatFindingRepository
from app.schemas.heartbeat import HeartbeatFindingRead, HeartbeatOperatorResponse, HeartbeatRunResponse
from redis.asyncio import Redis


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class _Candidate:
    dedupe_key: str
    finding_type: str
    severity: str
    summary: str
    mission_id: uuid.UUID | None = None
    approval_id: uuid.UUID | None = None
    worker_id: uuid.UUID | None = None
    integration_id: uuid.UUID | None = None
    service_component: str | None = None
    provenance_note: str | None = None


async def _pg_ok() -> tuple[bool, str | None]:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        return False, str(e)[:200]


async def _redis_ok(url: str) -> tuple[bool, str | None]:
    r = Redis.from_url(url, decode_responses=True)
    try:
        await asyncio.wait_for(r.ping(), timeout=2.0)
        return True, None
    except Exception as e:
        return False, str(e)[:200]
    finally:
        await r.close()


def _http_ok(url: str) -> tuple[bool, str | None]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            code = resp.getcode()
            if isinstance(code, int) and code < 500:
                return True, None
            return False, f"HTTP {code}"
    except urllib.error.HTTPError as e:
        return (e.code < 500, f"HTTP {e.code}")
    except Exception as e:
        return False, str(e)[:200]


async def _collect_candidates(session: AsyncSession) -> list[_Candidate]:
    """All checks are explicit; nothing is inferred from LLM output."""
    now = datetime.now(UTC)
    candidates: list[_Candidate] = []

    min_age_h = _float_env("HEARTBEAT_STALLED_MISSION_MIN_AGE_HOURS", 24.0)
    no_act_h = _float_env("HEARTBEAT_STALLED_NO_ACTIVITY_HOURS", 4.0)
    appr_h = _float_env("HEARTBEAT_AGING_APPROVAL_HOURS", 24.0)
    gap_min = _float_env("HEARTBEAT_RECEIPT_GAP_MINUTES", 30.0)
    worker_min = _float_env("HEARTBEAT_WORKER_STALE_MINUTES", 15.0)

    min_age_cutoff = now - timedelta(hours=min_age_h)
    no_act_cutoff = now - timedelta(hours=no_act_h)
    appr_cutoff = now - timedelta(hours=appr_h)
    gap_cutoff = now - timedelta(minutes=gap_min)
    worker_cutoff = now - timedelta(minutes=worker_min)

    # --- Stalled missions (old enough + no recent activity) ---
    q_stall = text(
        """
        SELECT m.id, m.title, m.status, m.created_at, m.updated_at,
               (SELECT MAX(created_at) FROM mission_events me WHERE me.mission_id = m.id) AS last_ev,
               (SELECT MAX(created_at) FROM receipts rx WHERE rx.mission_id = m.id) AS last_rx
        FROM missions m
        WHERE m.status IN ('active', 'pending', 'awaiting_approval')
        """
    )
    r = await session.execute(q_stall)
    for row in r.mappings().all():
        mid = row["id"]
        title = str(row["title"] or "")[:120]
        created_at = row["created_at"]
        updated_at = row["updated_at"]
        last_ev = row["last_ev"]
        last_rx = row["last_rx"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        if updated_at and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        acts = [created_at, updated_at, last_ev, last_rx]
        last_activity = max(x for x in acts if x is not None)
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=UTC)
        if created_at < min_age_cutoff and last_activity < no_act_cutoff:
            candidates.append(
                _Candidate(
                    dedupe_key=f"stalled_mission:{mid}",
                    finding_type="stalled_mission",
                    severity="medium",
                    summary=(
                        f"Mission «{title}» ({row['status']}) has had no mission/receipt activity since "
                        f"{last_activity.isoformat()} (threshold {no_act_h}h inactivity after "
                        f"{min_age_h}h mission age)."
                    ),
                    mission_id=mid,
                    provenance_note="Inferred from mission_events and receipts max(created_at); not user intent.",
                )
            )

    # --- Aging pending approvals ---
    q_appr = text(
        """
        SELECT a.id, a.mission_id, a.action_type, a.created_at
        FROM approvals a
        WHERE a.status = 'pending' AND a.created_at < :cutoff
        """
    )
    r2 = await session.execute(q_appr, {"cutoff": appr_cutoff})
    for row in r2.mappings().all():
        aid = row["id"]
        mid = row["mission_id"]
        candidates.append(
            _Candidate(
                dedupe_key=f"aging_approval:{aid}",
                finding_type="aging_approval",
                severity="high",
                summary=(
                    f"Pending approval ({row['action_type'][:80]}) since "
                    f"{row['created_at'].isoformat()} (>{appr_h}h)."
                ),
                mission_id=mid,
                approval_id=aid,
                provenance_note="Rule: approvals.status=pending and created_at older than threshold.",
            )
        )

    # --- Receipt gap: active-ish mission, no receipts, past grace window ---
    q_gap = text(
        """
        SELECT m.id, m.title, m.status, m.created_at
        FROM missions m
        WHERE m.status IN ('active', 'pending')
          AND m.created_at < :gap_cutoff
          AND NOT EXISTS (SELECT 1 FROM receipts r WHERE r.mission_id = m.id)
        """
    )
    r3 = await session.execute(q_gap, {"gap_cutoff": gap_cutoff})
    for row in r3.mappings().all():
        mid = row["id"]
        title = str(row["title"] or "")[:120]
        candidates.append(
            _Candidate(
                dedupe_key=f"receipt_gap:{mid}",
                finding_type="receipt_gap",
                severity="medium",
                summary=(
                    f"No execution receipts recorded for «{title}» after "
                    f"{gap_min}m (mission still {row['status']})."
                ),
                mission_id=mid,
                provenance_note="Rule: no rows in receipts for mission_id; execution path may not have run.",
            )
        )

    # --- Stale workers (recency from last_heartbeat_at only) ---
    q_w = text(
        """
        SELECT w.id, w.name, w.worker_type, w.status, w.last_heartbeat_at
        FROM workers w
        WHERE w.last_heartbeat_at IS NULL OR w.last_heartbeat_at < :cutoff
        """
    )
    r4 = await session.execute(q_w, {"cutoff": worker_cutoff})
    for row in r4.mappings().all():
        wid = row["id"]
        nm = str(row["name"] or "worker")
        lb = row["last_heartbeat_at"]
        if lb is not None:
            prov = (
                "Direct: last worker heartbeat older than threshold "
                f"(POST /api/v1/workers/heartbeat); last at {lb.isoformat()}."
            )
        else:
            prov = (
                "Direct: worker row has no heartbeat timestamp yet "
                "(expecting POST /api/v1/workers/heartbeat)."
            )
        candidates.append(
            _Candidate(
                dedupe_key=f"stale_worker:{wid}",
                finding_type="stale_worker",
                severity="medium",
                summary=(
                    f"Worker «{nm}» ({row['worker_type']}) last heartbeat: "
                    f"{lb.isoformat() if lb else 'never'} (threshold {worker_min}m)."
                ),
                worker_id=wid,
                provenance_note=prov,
            )
        )

    # --- System components (same probes as /system/health; explicit degraded/offline) ---
    settings = get_settings()
    ok, err = await _pg_ok()
    if not ok:
        candidates.append(
            _Candidate(
                dedupe_key="system_degraded:postgres",
                finding_type="system_degraded",
                severity="critical",
                summary=f"PostgreSQL probe failed: {err}",
                service_component="postgres",
                provenance_note="Control-plane DB connectivity check (SELECT 1).",
            )
        )
    redis_url = settings.REDIS_URL or "redis://localhost:6379"
    rok, rerr = await _redis_ok(redis_url)
    if not rok:
        candidates.append(
            _Candidate(
                dedupe_key="system_degraded:redis",
                finding_type="system_degraded",
                severity="high",
                summary=f"Redis probe failed: {rerr}",
                service_component="redis",
                provenance_note="PING from control plane host.",
            )
        )
    gw = settings.JARVIS_HEALTH_OPENCLAW_GATEWAY_URL.strip() or "http://127.0.0.1:18789/health"
    gok, gerr = await asyncio.to_thread(_http_ok, gw)
    if not gok:
        candidates.append(
            _Candidate(
                dedupe_key="system_degraded:openclaw_gateway",
                finding_type="system_degraded",
                severity="high",
                summary=f"OpenClaw gateway HTTP probe failed ({gw}): {gerr}",
                service_component="openclaw_gateway",
                provenance_note="HTTP GET from control plane; same URL family as system health.",
            )
        )

    # --- Integration attention (DB truth only) ---
    q_int = text(
        """
        SELECT id, name, status FROM integrations
        WHERE status IN ('needs_auth', 'not_configured', 'degraded', 'unknown')
        LIMIT 50
        """
    )
    r5 = await session.execute(q_int)
    for row in r5.mappings().all():
        iid = row["id"]
        candidates.append(
            _Candidate(
                dedupe_key=f"integration_attention:{iid}",
                finding_type="integration_attention",
                severity="low",
                summary=f"Integration «{row['name']}» status={row['status']} (DB row).",
                integration_id=iid,
                provenance_note="integrations.status from control plane DB only.",
            )
        )

    # --- Cost guardrails (cost_events rolling window vs explicit env thresholds) ---
    for cc in await collect_cost_guardrail_candidates(session, now):
        candidates.append(
            _Candidate(
                dedupe_key=cc.dedupe_key,
                finding_type=cc.finding_type,
                severity=cc.severity,
                summary=cc.summary,
                provenance_note=cc.provenance_note,
                service_component="cost_guardrails",
            )
        )

    return candidates


async def _upsert_candidate(session: AsyncSession, c: _Candidate, now: datetime) -> str:
    """Returns 'inserted' | 'updated'."""
    existing = await HeartbeatFindingRepository.get_by_dedupe_key(session, c.dedupe_key)
    if existing is None:
        row = HeartbeatFinding(
            id=uuid.uuid4(),
            finding_type=c.finding_type,
            severity=c.severity,
            summary=c.summary,
            dedupe_key=c.dedupe_key,
            mission_id=c.mission_id,
            approval_id=c.approval_id,
            worker_id=c.worker_id,
            integration_id=c.integration_id,
            service_component=c.service_component,
            provenance_note=c.provenance_note,
            status="open",
            first_seen_at=now,
            last_seen_at=now,
            resolved_at=None,
        )
        await HeartbeatFindingRepository.save(session, row)
        return "inserted"

    existing.last_seen_at = now
    existing.summary = c.summary
    existing.severity = c.severity
    existing.mission_id = c.mission_id
    existing.approval_id = c.approval_id
    existing.worker_id = c.worker_id
    existing.integration_id = c.integration_id
    existing.service_component = c.service_component
    existing.provenance_note = c.provenance_note
    if existing.status == "resolved":
        existing.status = "open"
        existing.resolved_at = None
    await session.flush()
    return "updated"


async def run_heartbeat_cycle(session: AsyncSession) -> HeartbeatRunResponse:
    now = datetime.now(UTC)
    await run_approval_reminder_cycle(session)
    candidates = await _collect_candidates(session)
    keys = {c.dedupe_key for c in candidates}

    upserted = 0
    for c in candidates:
        await _upsert_candidate(session, c, now)
        upserted += 1

    resolved = 0
    open_rows = await HeartbeatFindingRepository.list_open(session)
    for row in open_rows:
        if row.dedupe_key not in keys:
            row.status = "resolved"
            row.resolved_at = now
            resolved += 1
    await session.flush()

    open_list = await HeartbeatFindingRepository.list_open(session)
    return HeartbeatRunResponse(
        evaluated_at=now.isoformat().replace("+00:00", "Z"),
        open_count=len(open_list),
        resolved_this_run=resolved,
        upserted=upserted,
    )


async def build_operator_snapshot(session: AsyncSession) -> HeartbeatOperatorResponse:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    rows = await HeartbeatFindingRepository.list_open(session)
    by_sev: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for r in rows:
        by_sev[r.severity] = by_sev.get(r.severity, 0) + 1
        by_type[r.finding_type] = by_type.get(r.finding_type, 0) + 1
    return HeartbeatOperatorResponse(
        generated_at=now,
        open_count=len(rows),
        by_severity=by_sev,
        by_type=by_type,
        open_findings=[HeartbeatFindingRead.model_validate(x) for x in rows],
    )


def finding_to_activity_meta(row: HeartbeatFinding) -> dict[str, Any]:
    return {
        "provenance": "heartbeat_finding",
        "finding_type": row.finding_type,
        "severity": row.severity,
        "dedupe_key": row.dedupe_key,
        "mission_id": str(row.mission_id) if row.mission_id else None,
        "approval_id": str(row.approval_id) if row.approval_id else None,
        "worker_id": str(row.worker_id) if row.worker_id else None,
        "integration_id": str(row.integration_id) if row.integration_id else None,
        "service_component": row.service_component,
        "provenance_note": row.provenance_note,
    }
