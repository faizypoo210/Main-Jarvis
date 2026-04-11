"""Conservative promotion — only structured candidates; no log/receipt dumps."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.receipt import Receipt
from app.schemas.memory import MEMORY_TYPES

_MAX_TITLE = 512
_MAX_SUMMARY = 8000
_MAX_CONTENT = 64000


def _clean_str(v: Any, max_len: int) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    return s[:max_len]


def parse_receipt_memory_candidate(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return a normalized candidate dict or None if missing/invalid."""
    raw = payload.get("memory_candidate")
    if not isinstance(raw, dict):
        return None
    mtype = raw.get("memory_type")
    title = raw.get("title")
    if not isinstance(mtype, str) or not isinstance(title, str):
        return None
    mtype = mtype.strip()
    title = title.strip()
    if mtype not in MEMORY_TYPES or not title or len(title) > _MAX_TITLE:
        return None
    summary = _clean_str(raw.get("summary"), _MAX_SUMMARY)
    content = _clean_str(raw.get("content"), _MAX_CONTENT)
    if not summary and not content:
        # Require at least one durable body field beyond title
        return None
    tags = raw.get("tags")
    tag_list: list[str] = []
    if isinstance(tags, list):
        for t in tags[:32]:
            if isinstance(t, str) and t.strip():
                tag_list.append(t.strip()[:64])
    dedupe = raw.get("dedupe_key")
    dedupe_s: str | None = None
    if isinstance(dedupe, str) and dedupe.strip():
        dedupe_s = dedupe.strip()[:256]
    return {
        "memory_type": mtype,
        "title": title,
        "summary": summary,
        "content": content,
        "tags": tag_list,
        "dedupe_key": dedupe_s,
    }


def parse_system_memory_candidate(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Optional `system_memory_candidate` with same shape as receipt (explicit system path)."""
    raw = payload.get("system_memory_candidate")
    if not isinstance(raw, dict):
        return None
    return parse_receipt_memory_candidate({"memory_candidate": raw})
