from __future__ import annotations

import logging
import os
from typing import Any

import httpx

log = logging.getLogger("jarvis.fast_research")

_SEARCH_TIMEOUT = 8.0
_SYNTHESIS_TIMEOUT = 20.0


async def _search(query: str) -> list[dict[str, Any]]:
    """DuckDuckGo Instant Answer API — no auth, no key required.

    Returns list of result dicts with 'title' and 'snippet' keys.
    Returns empty list on any failure."""
    try:
        ddgo_url = os.environ.get("JARVIS_SEARCH_URL", "https://api.duckduckgo.com/").strip()
        async with httpx.AsyncClient(timeout=_SEARCH_TIMEOUT) as client:
            r = await client.get(
                ddgo_url,
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            )
            r.raise_for_status()
            data = r.json()
            results: list[dict[str, Any]] = []
            # AbstractText is the best single answer
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", query),
                    "snippet": data["AbstractText"][:400],
                })
            # RelatedTopics give breadth
            for topic in (data.get("RelatedTopics") or [])[:4]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("FirstURL", ""),
                        "snippet": topic["Text"][:300],
                    })
            return results[:5]
    except Exception as e:
        log.warning("fast_research search failed: %s", e)
        return []


async def _synthesize(query: str, results: list[dict[str, Any]]) -> str:
    """Synthesize search results into a Jarvis-voiced answer using local or cloud model.

    Tries JARVIS_LOCAL_MODEL via Ollama first. Falls back to plain summary on failure."""
    base = os.environ.get("OLLAMA_BASE_URL", "").strip().rstrip("/")
    model = os.environ.get("JARVIS_LOCAL_MODEL", "").strip()
    if not results:
        return f"I was unable to find current information on {query}, sir."
    context_text = "\n".join(
        f"- {r['title']}: {r['snippet']}" for r in results if r.get("snippet")
    )
    cloud_model = os.environ.get("JARVIS_CLOUD_MODEL", "").strip()
    if not base or not model:
        if cloud_model:
            log.info("fast_research: JARVIS_CLOUD_MODEL set (%s) but cloud synthesis not yet wired; using plain summary", cloud_model)
        return f"Here is what I found on {query}:\n{context_text}"
    prompt = (
        f"You are JARVIS, a governed executive AI assistant. "
        f'The operator asked: "{query}"\n\n'
        f"Here is the research data:\n{context_text}\n\n"
        f"Write a concise, direct answer in 2-4 sentences. "
        f"Address the operator as 'sir'. "
        f"Do not mention the search sources. "
        f"Reply with only the answer."
    )
    try:
        async with httpx.AsyncClient(timeout=_SYNTHESIS_TIMEOUT) as client:
            r = await client.post(
                f"{base}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "think": False},
            )
            r.raise_for_status()
            answer = r.json().get("response", "").strip()
            if not answer:
                raise ValueError("empty synthesis response")
            return answer
    except Exception as e:
        log.warning("fast_research synthesis failed: %s", e)
        return f"Here is what I found on {query}:\n{context_text}"


async def run_fast_research(query: str) -> tuple[str, str]:
    """Entry point. Returns (display_text, spoken_text).

    Total soft budget: ~30s. Never raises."""
    try:
        results = await _search(query)
        display = await _synthesize(query, results)
        # spoken_text: first two sentences only
        sentences = [s.strip() for s in display.split(".") if s.strip()]
        spoken = ". ".join(sentences[:2]) + "." if sentences else display
        return display, spoken
    except Exception as e:
        log.error("fast_research run failed: %s", e)
        fallback = f"I was unable to complete research on that request, sir."
        return fallback, fallback
