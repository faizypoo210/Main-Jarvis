"""Derive and persist cost_events from receipts — sparse direct truth, no fake USD."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost_event import CostEvent
from app.models.receipt import Receipt


def _as_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _as_decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if d < 0:
        return None
    return d


def derive_cost_event_from_receipt(receipt: Receipt) -> dict[str, Any]:
    """Build CostEvent column values from receipt row. Never invent billing amounts."""
    rt = receipt.receipt_type or ""
    payload: dict[str, Any] = receipt.payload if isinstance(receipt.payload, dict) else {}
    mission_id: UUID | None = receipt.mission_id

    if rt == "openclaw_execution":
        tin: int | None = None
        tout: int | None = None
        usage = payload.get("usage")
        if isinstance(usage, dict):
            tin = _as_int(usage.get("prompt_tokens") or usage.get("input_tokens"))
            tout = _as_int(usage.get("completion_tokens") or usage.get("output_tokens"))
        if tin is None:
            tin = _as_int(payload.get("usage_tokens_input") or payload.get("token_input"))
        if tout is None:
            tout = _as_int(payload.get("usage_tokens_output") or payload.get("token_output"))

        cost_usd: Decimal | None = None
        raw_cost = payload.get("cost_usd")
        if raw_cost is None and isinstance(usage, dict):
            raw_cost = usage.get("cost_usd") or usage.get("total_cost_usd")
        cost_usd = _as_decimal(raw_cost)

        est_usd = _as_decimal(payload.get("estimated_cost_usd"))

        em = payload.get("execution_meta")
        lane = None
        if isinstance(em, dict):
            lane = em.get("lane")
        operation = str(lane or "openclaw_execution")[:256]

        usage_units: dict[str, Any] | None = None
        if isinstance(usage, dict) and usage:
            usage_units = {k: usage[k] for k in usage if k in usage}

        if cost_usd is not None and cost_usd > 0:
            return {
                "mission_id": mission_id,
                "source_kind": "execution",
                "source_receipt_id": receipt.id,
                "provider": "openclaw",
                "operation": operation,
                "amount": cost_usd,
                "currency": "USD",
                "cost_status": "direct",
                "usage_tokens_input": tin,
                "usage_tokens_output": tout,
                "usage_units": usage_units,
                "notes": None,
            }

        if est_usd is not None and est_usd > 0:
            return {
                "mission_id": mission_id,
                "source_kind": "execution",
                "source_receipt_id": receipt.id,
                "provider": "openclaw",
                "operation": operation,
                "amount": est_usd,
                "currency": "USD",
                "cost_status": "estimated",
                "usage_tokens_input": tin,
                "usage_tokens_output": tout,
                "usage_units": usage_units,
                "notes": "estimated_cost_usd from receipt payload (not metered billing).",
            }

        if tin is not None or tout is not None:
            return {
                "mission_id": mission_id,
                "source_kind": "execution",
                "source_receipt_id": receipt.id,
                "provider": "openclaw",
                "operation": operation,
                "amount": None,
                "currency": None,
                "cost_status": "unknown",
                "usage_tokens_input": tin,
                "usage_tokens_output": tout,
                "usage_units": usage_units,
                "notes": "Token usage present in receipt; USD not provided in payload.",
            }

        return {
            "mission_id": mission_id,
            "source_kind": "execution",
            "source_receipt_id": receipt.id,
            "provider": "openclaw",
            "operation": operation,
            "amount": None,
            "currency": None,
            "cost_status": "unknown",
            "usage_tokens_input": None,
            "usage_tokens_output": None,
            "usage_units": None,
            "notes": "No token or USD usage in receipt payload (OpenClaw path).",
        }

    if rt.startswith("github_"):
        return {
            "mission_id": mission_id,
            "source_kind": "integration",
            "source_receipt_id": receipt.id,
            "provider": "github",
            "operation": rt[:256],
            "amount": None,
            "currency": None,
            "cost_status": "not_applicable",
            "usage_tokens_input": None,
            "usage_tokens_output": None,
            "usage_units": None,
            "notes": "GitHub REST usage; no Jarvis-metered cloud spend on this receipt.",
        }

    if rt.startswith("gmail_"):
        return {
            "mission_id": mission_id,
            "source_kind": "integration",
            "source_receipt_id": receipt.id,
            "provider": "gmail",
            "operation": rt[:256],
            "amount": None,
            "currency": None,
            "cost_status": "not_applicable",
            "usage_tokens_input": None,
            "usage_tokens_output": None,
            "usage_units": None,
            "notes": "Gmail API usage; no Jarvis-metered cloud spend on this receipt.",
        }

    return {
        "mission_id": mission_id,
        "source_kind": "system",
        "source_receipt_id": receipt.id,
        "provider": None,
        "operation": rt[:256] if rt else None,
        "amount": None,
        "currency": None,
        "cost_status": "unknown",
        "usage_tokens_input": None,
        "usage_tokens_output": None,
        "usage_units": None,
        "notes": f"Receipt type «{rt}»; no specific cost classification.",
    }


async def record_cost_event_for_receipt(db: AsyncSession, receipt: Receipt) -> None:
    """Idempotent: one cost row per receipt when source_receipt_id is set."""
    r = await db.execute(
        select(CostEvent.id).where(CostEvent.source_receipt_id == receipt.id).limit(1)
    )
    if r.scalar_one_or_none() is not None:
        return

    data = derive_cost_event_from_receipt(receipt)
    ev = CostEvent(**data)
    db.add(ev)
    await db.flush()
