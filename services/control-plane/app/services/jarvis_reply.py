"""Compose operator context and obtain a Jarvis reply (local Ollama HTTP) with safe fallback.

TRUTH_SOURCE: OLLAMA_BASE_URL + JARVIS_LOCAL_MODEL for POST /api/generate; OpenClaw CLI reserved for missions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Literal

import httpx

from app.core.config import get_settings
from shared.reply import build_jarvis_reply

log = logging.getLogger(__name__)

Source = Literal["ollama", "fallback"]

_SKIP_STDOUT_PREFIXES = ("🦞", "Config warnings", "╭", "╰", "│", "◇", "◆")


def _openclaw_cmd() -> str:
    return os.getenv(
        "OPENCLAW_CMD",
        str(Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"),
    )


def _agent_timeout_sec() -> float:
    raw = (os.getenv("JARVIS_OPENCLAW_AGENT_TIMEOUT_SEC") or "").strip()
    if not raw:
        return 120.0
    try:
        v = float(raw)
        return max(15.0, min(v, 900.0))
    except ValueError:
        return 120.0


def _compose_context_block(
    *,
    user_text: str,
    active_missions: list[tuple[str, str]],
    pending_approval_count: int,
    recent_receipt_summaries: list[str | None],
    memory_items: list[str],
) -> str:
    lines: list[str] = []
    lines.append("## Control plane snapshot (authoritative)")
    if active_missions:
        lines.append("### Active missions (title — status)")
        for title, status in active_missions:
            lines.append(f"- {title} — {status}")
    else:
        lines.append("### Active missions")
        lines.append("- (none)")
    lines.append(f"### Pending approvals: {pending_approval_count}")
    lines.append("### Recent receipts (newest first, up to 3)")
    if recent_receipt_summaries:
        for s in recent_receipt_summaries:
            t = (s or "").strip()
            lines.append(f"- {t}" if t else "- (no summary)")
    else:
        lines.append("- (none)")
    lines.append("")
    if memory_items:
        lines.append("## Operator Memory")
        for m in memory_items:
            lines.append(f"- {m}")
        lines.append("")
    lines.append("## Operator message")
    lines.append(user_text.strip())
    return "\n".join(lines).strip()


def _first_json_object(text: str) -> dict[str, Any] | None:
    s = text.strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _extract_reply_from_openclaw_json(obj: dict[str, Any]) -> str | None:
    """Best-effort parse of `openclaw agent --json` stdout (schema may vary by version)."""

    def walk(o: Any) -> str | None:
        if isinstance(o, str):
            t = o.strip()
            return t or None
        if isinstance(o, dict):
            for key in (
                "message",
                "reply",
                "text",
                "content",
                "assistantMessage",
                "output",
                "body",
                "result",
                "response",
            ):
                if key in o:
                    got = walk(o[key])
                    if got:
                        return got
            for v in o.values():
                got = walk(v)
                if got:
                    return got
        if isinstance(o, list):
            for item in reversed(o):
                got = walk(item)
                if got:
                    return got
        return None

    return walk(obj)


def _clean_cli_stdout_lines(output: str) -> str:
    lines = output.splitlines()
    clean: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(p) for p in _SKIP_STDOUT_PREFIXES):
            continue
        clean.append(stripped)
    return "\n".join(clean).strip()


def _local_fallback_summary(
    *,
    user_text: str,
    active_missions: list[tuple[str, str]],
    pending_approval_count: int,
    recent_receipt_summaries: list[str | None],
) -> str:
    parts: list[str] = []
    parts.append("I could not reach the local model (Ollama) for a full reply.")
    if active_missions:
        parts.append(
            f"Active missions ({len(active_missions)}): "
            + "; ".join(f"{t} ({s})" for t, s in active_missions[:8])
        )
    else:
        parts.append("No active missions in flight.")
    parts.append(f"Pending approvals: {pending_approval_count}.")
    if recent_receipt_summaries:
        rs = [x for x in recent_receipt_summaries if (x or "").strip()]
        if rs:
            parts.append("Recent receipts: " + " | ".join(r.strip() for r in rs[:3]))
    parts.append(f'Your question was: "{user_text.strip()}"')
    return " ".join(parts)


def _load_soul() -> str:
    """Load SOUL.md from workspace. Returns a minimal fallback if missing."""
    candidates = [
        Path(os.environ.get("JARVIS_WORKSPACE_DIR", "")) / "SOUL.md",
        Path.home() / ".openclaw" / "workspace" / "main" / "SOUL.md",
    ]
    for p in candidates:
        try:
            text = p.read_text(encoding="utf-8").strip()
            if text:
                return text
        except Exception:
            continue
    return (
        "You are Jarvis — an executive AI command center. "
        "You are calm, competent, and direct. You think in missions. "
        "Your operator is Faiz. Never say you are Qwen or any other model. "
        "Keep replies brief unless depth is needed."
    )


async def _ollama_generate(prompt: str) -> str | None:
    """POST ``/api/generate`` on Ollama; base URL and model from env only."""
    settings = get_settings()
    base = (settings.OLLAMA_BASE_URL or "http://127.0.0.1:11434").strip().rstrip("/")
    model = (settings.JARVIS_LOCAL_MODEL or "").strip()
    if not model:
        return None
    url = f"{base}/api/generate"
    soul = _load_soul()
    body = {
        "model": model,
        "prompt": prompt,
        "system": soul,
        "stream": False,
        "think": False,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as client:
            r = await client.post(url, json=body)
    except Exception as e:
        log.warning("ollama generate request failed: %s", e)
        return None
    if r.status_code >= 400:
        log.warning("ollama generate HTTP %s", r.status_code)
        return None
    try:
        data = r.json()
    except Exception as e:
        log.warning("ollama generate invalid JSON: %s", e)
        return None
    if not isinstance(data, dict):
        return None
    text = data.get("response")
    if isinstance(text, str):
        t = text.strip()
        return t or None
    return None


# Reserved for mission execution (Slice 4+)
async def _run_openclaw_agent_json(prompt: str) -> str | None:
    cmd = _openclaw_cmd()
    timeout = _agent_timeout_sec()
    try:
        proc = await asyncio.create_subprocess_exec(
            cmd,
            "agent",
            "--agent",
            "main",
            "--message",
            prompt,
            "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except (FileNotFoundError, OSError) as e:
        log.warning("openclaw agent launch failed: %s", e)
        return None

    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        log.warning("openclaw agent timed out after %ss", timeout)
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return None

    out = stdout_b.decode("utf-8", errors="replace") if stdout_b else ""
    err = stderr_b.decode("utf-8", errors="replace") if stderr_b else ""
    if err.strip():
        log.debug("openclaw agent stderr: %s", err.strip()[:500])

    parsed = _first_json_object(out)
    if parsed is not None:
        extracted = _extract_reply_from_openclaw_json(parsed)
        if extracted:
            return extracted

    cleaned = _clean_cli_stdout_lines(out)
    return cleaned or None


async def build_reply(
    user_text: str,
    active_missions: list[tuple[str, str]],
    pending_approvals: int,
    recent_receipts: list[str | None],
    memory_items: list[str] | None = None,
) -> tuple[str, Source]:
    """Return (reply, source). Never raises: failures yield deterministic fallback text."""
    ut = (user_text or "").strip()
    if not ut:
        return (
            build_jarvis_reply("unknown", "", surface="command_center"),
            "fallback",
        )

    missions = list(active_missions)
    summaries = list(recent_receipts)
    mems = list(memory_items) if memory_items is not None else []
    try:
        block = _compose_context_block(
            user_text=ut,
            active_missions=missions,
            pending_approval_count=int(pending_approvals),
            recent_receipt_summaries=summaries,
            memory_items=mems,
        )

        ollama_reply = await _ollama_generate(block)
        if ollama_reply and ollama_reply.strip():
            return ollama_reply.strip(), "ollama"
    except Exception as e:
        log.warning("build_reply: ollama path failed: %s", e)

    fb = _local_fallback_summary(
        user_text=ut,
        active_missions=missions,
        pending_approval_count=int(pending_approvals),
        recent_receipt_summaries=summaries,
    )
    return build_jarvis_reply("local_fallback", fb, surface="command_center"), "fallback"
