"""Voice handler precedence — defer specialized briefing when text is mission-style work.

Briefing is for **operator snapshot** questions (what is happening, what needs attention).
Phrases that ask to **check / summarize / review** external systems (GitHub, PRs, Gmail, …)
should fall through to unified intake as free-form missions.

TRUTH_SOURCE: ``server.py`` order is inbox → briefing → governed → approval → intake.
"""

from __future__ import annotations

import re

# Mission / investigation verbs (not operator meta-questions like "what's blocked overall").
_RE_WORK_ON_EXTERNAL = re.compile(
    r"\b("
    r"check|summarize|summarise|look\s+through|review|scan|inspect|audit|analyze|analyse|"
    r"investigate|research|compare|list|read|show|find|open|pull\s+up|give\s+me\s+an?\s+overview\s+of"
    r")\b",
    re.I,
)

_RE_EXTERNAL_SCOPE = re.compile(
    r"\b("
    r"github|pull\s+request|pull\s+requests|\bpr\b|\bprs\b|issues?|"
    r"gmail|mailbox|email|draft|\binbox\b"
    r")\b",
    re.I,
)

# Operator-only briefing phrases — still use briefing even if they mention GitHub in passing.
_RE_OPERATOR_BRIEFING_PREFIX = re.compile(
    r"^\s*("
    r"what\s+is\s+happening|what'?s\s+happening|what\s+is\s+going\s+on|what'?s\s+going\s+on|"
    r"what\s+needs\s+my\s+attention|what\s+should\s+I\s+focus\s+on|"
    r"give\s+me\s+a\s+status|status\s+overview|big\s+picture|"
    r"what\s+am\s+I\s+working\s+on|what\s+are\s+we\s+working\s+on|"
    r"what'?s\s+running|what\s+is\s+running|"
    r"what'?s\s+blocked|what\s+is\s+blocked|what\s+is\s+stuck|"
    r"what\s+changed\s+recently|what\s+is\s+new|recent\s+changes"
    r")\b",
    re.I,
)


def should_defer_briefing_to_freeform_intake(text: str) -> bool:
    """Return True to skip briefing and let ``POST /api/v1/intake`` classify the utterance."""
    t = " ".join(text.lower().strip().split())
    if not t:
        return False
    if _RE_OPERATOR_BRIEFING_PREFIX.match(t):
        return False
    if not _RE_WORK_ON_EXTERNAL.search(t):
        return False
    if not _RE_EXTERNAL_SCOPE.search(t):
        return False
    return True
