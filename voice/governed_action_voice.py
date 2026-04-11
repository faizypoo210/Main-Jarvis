"""
Voice Governed Action Requests v1 — narrow approval-gated POSTs to mission integration routes.

Creates pending approvals only (requested_via=voice). Same routes as Command Center launchers.
Ephemeral per-WebSocket draft state; not mission authority.

TRUTH_SOURCE: POST /api/v1/missions/{id}/integrations/github/* and /gmail/* with x-api-key.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger("jarvis.voice.governed_action")

_REPO_RE = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
_UUID_FULL = re.compile(
    r"\b([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\b",
    re.I,
)
_UUID_PREFIX = re.compile(r"\b([0-9a-f]{8,32})\b", re.I)

RE_CANCEL = re.compile(
    r"\b(cancel\s+that|never\s+mind|forget\s+it|abort(\s+this)?|discard(\s+that)?)\b",
    re.I,
)
RE_CONFIRM = re.compile(
    r"^(yes|confirm|submit(\s+it)?|go\s+ahead|that'?s\s+(right|correct)|sounds?\s+good)(\s*[.!]?)?$",
    re.I,
)
RE_LAST_MISSION = re.compile(
    r"\b(last\s+mission|use\s+last|previous\s+mission|the\s+last\s+one)\b",
    re.I,
)
# Vague execution phrases — never treat as submit outside explicit confirm wording
RE_VAGUE_DO = re.compile(
    r"^(do\s+it|send\s+it|merge\s+it|ship\s+it|just\s+do\s+it)(\s*[.!]?)?$",
    re.I,
)

# --- Start intents (narrow) ---
RE_START_GH_ISSUE = re.compile(
    r"\b(create|open|file)\s+(a\s+)?github\s+issue\b",
    re.I,
)
RE_START_GH_PR = re.compile(
    r"\b(open|create)\s+(a\s+)?github\s+draft\s+(pr|pull\s+request)\b|"
    r"\bcreate\s+(a\s+)?draft\s+(pull\s+request|pr)\b",
    re.I,
)
RE_START_GH_MERGE = re.compile(
    r"\bmerge\s+(a\s+)?github\s+(pr|pull\s+request)\b|\bmerge\s+(the\s+)?pull\s+request\b",
    re.I,
)
# Inline: merge PR 12 in org/repo
RE_INLINE_GH_MERGE = re.compile(
    r"\bmerge\s+(?:github\s+)?(?:pr|pull\s+request)\s+(\d{1,7})\s+(?:in|for)\s+([a-z0-9_.-]+/[a-z0-9_.-]+)\b",
    re.I,
)
RE_START_GM_DRAFT = re.compile(
    r"\b(draft\s+(an?\s+)?email|create\s+(a\s+)?gmail\s+draft|compose\s+(an?\s+)?email)\b",
    re.I,
)
RE_START_GM_SEND = re.compile(
    r"\bsend\s+(a\s+)?gmail\s+draft\b|\bsend\s+(the\s+)?draft\b",
    re.I,
)
RE_INLINE_GM_SEND = re.compile(
    r"\bsend\s+gmail\s+draft\s+([a-zA-Z0-9_-]{6,256})\b",
    re.I,
)
RE_START_GM_REPLY = re.compile(
    r"\b(create\s+(a\s+)?)?gmail\s+reply\s+draft\b|\breply\s+draft\b",
    re.I,
)

_drafts: dict[int, GovernedDraft] = {}
_last_mission_by_ws: dict[int, str] = {}

# Cached GET /api/v1/operator/action-catalog (launch metadata only; no secrets).
_catalog_cache: dict[str, Any] | None = None
_catalog_load_failed: bool = False


@dataclass
class GovernedDraft:
    kind: str
    fields: dict[str, str] = field(default_factory=dict)
    step: str = "collect"  # collect | confirm


def forget_voice_governed_action_state(ws_key: int) -> None:
    _drafts.pop(ws_key, None)
    _last_mission_by_ws.pop(ws_key, None)


def note_voice_command_mission(ws_key: int, mission_id: str) -> None:
    if mission_id.strip():
        _last_mission_by_ws[ws_key] = str(mission_id).strip()


def _norm(s: str) -> str:
    return " ".join(s.lower().strip().split())


def _requested_by() -> str:
    import os

    return (os.environ.get("JARVIS_VOICE_REQUESTED_BY") or "voice_operator").strip() or "voice_operator"


def _short_id(full_id: str) -> str:
    s = str(full_id).replace("-", "")
    return s[:8] if len(s) >= 8 else s


def _get_draft(ws_key: int) -> GovernedDraft | None:
    return _drafts.get(ws_key)


def _clear_draft(ws_key: int) -> None:
    _drafts.pop(ws_key, None)


def _error_detail(resp: httpx.Response) -> str:
    try:
        j = resp.json()
        d = j.get("detail")
        if isinstance(d, str):
            return d[:400]
        if isinstance(d, list) and d:
            return str(d)[:400]
    except Exception:
        pass
    t = resp.text or ""
    return (t[:400] if t else f"HTTP {resp.status_code}")


async def _fetch_missions(client: httpx.AsyncClient, base: str, api_key: str) -> list[dict[str, Any]]:
    headers = {"x-api-key": api_key, "Accept": "application/json"}
    r = await client.get(f"{base}/api/v1/missions?limit=200", headers=headers, timeout=25.0)
    r.raise_for_status()
    body = r.json()
    return list(body) if isinstance(body, list) else []


async def _resolve_mission_id(
    utterance: str,
    client: httpx.AsyncClient,
    base: str,
    api_key: str,
    ws_key: int,
) -> tuple[str | None, str | None]:
    """
    Return (mission_id, error_message) — error_message set if resolution failed.
    """
    t = utterance.strip()
    low = _norm(t)

    if RE_LAST_MISSION.search(low):
        mid = _last_mission_by_ws.get(ws_key)
        if not mid:
            return None, "There is no recent mission from a voice command yet. Say a mission id."
        return mid, None

    m = _UUID_FULL.search(t)
    if m:
        cand = m.group(1)
        try:
            r = await client.get(
                f"{base}/api/v1/missions/{cand}",
                headers={"x-api-key": api_key, "Accept": "application/json"},
                timeout=20.0,
            )
            if r.status_code == 200:
                return cand, None
        except Exception as e:
            log.warning("mission get: %s", e)
        return None, f"I could not find mission {cand[:8]}."

    m2 = _UUID_PREFIX.search(t)
    token = None
    if m2:
        token = re.sub(r"[^a-f0-9]", "", m2.group(1).lower())
    if not token or len(token) < 8:
        return None, None  # not a mission token in this utterance

    try:
        missions = await _fetch_missions(client, base, api_key)
    except Exception as e:
        log.warning("missions list: %s", e)
        return None, "I could not load missions from the control plane."

    matches: list[str] = []
    for row in missions:
        mid = str(row.get("id") or "")
        compact = mid.replace("-", "").lower()
        if compact.startswith(token) or token in compact:
            matches.append(mid)

    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, "That prefix matches more than one mission. Say the full mission id."
    return None, f"No mission matches id starting with {token[:8]}."


def _field_order_legacy(kind: str) -> list[str]:
    if kind == "gh_issue":
        return ["mission_id", "repo", "title", "body"]
    if kind == "gh_pr":
        return ["mission_id", "repo", "base", "head", "title", "body"]
    if kind == "gh_merge":
        return ["mission_id", "repo", "pull_number"]
    if kind == "gm_draft":
        return ["mission_id", "to", "subject", "body"]
    if kind == "gm_send":
        return ["mission_id", "draft_id"]
    if kind == "gm_reply":
        return ["mission_id", "reply_to_message_id", "body", "thread_id"]
    return []


def _catalog_entry_for_voice(kind: str) -> dict[str, Any] | None:
    global _catalog_cache
    if not _catalog_cache or not isinstance(_catalog_cache.get("actions"), list):
        return None
    for a in _catalog_cache["actions"]:
        if isinstance(a, dict) and a.get("voice_internal_kind") == kind:
            return a
    return None


def _voice_body_field_names(entry: dict[str, Any]) -> list[str]:
    """Catalog field_order minus voice-silent checkboxes (e.g. draft default)."""
    order = list(entry.get("field_order") or [])
    fields_list = list(entry.get("fields") or [])
    by_name = {str(f.get("name")): f for f in fields_list if isinstance(f, dict)}
    out: list[str] = []
    for name in order:
        fld = by_name.get(name)
        if not isinstance(fld, dict):
            continue
        if fld.get("type") == "checkbox" and fld.get("voice_prompt") in (None, ""):
            continue
        out.append(name)
    return out


def _field_order(kind: str) -> list[str]:
    entry = _catalog_entry_for_voice(kind)
    if entry:
        return ["mission_id"] + _voice_body_field_names(entry)
    return _field_order_legacy(kind)


def _prompt_for(kind: str, field: str) -> str:
    if field == "mission_id":
        return (
            "Which mission should this attach to? Say last for the mission from your last voice command, "
            "or say the mission id or the first eight characters."
        )
    entry = _catalog_entry_for_voice(kind)
    if entry:
        for f in entry.get("fields") or []:
            if isinstance(f, dict) and f.get("name") == field:
                vp = f.get("voice_prompt")
                if isinstance(vp, str) and vp.strip():
                    return vp
                break
    if field == "repo":
        return "Say the GitHub repository as owner slash name, like acme slash repo."
    if field == "title":
        return "Say the title."
    if field == "body":
        return "Say the body text, or say skip for empty."
    if field == "base":
        return "Say the base branch name."
    if field == "head":
        return "Say the head branch or user colon branch."
    if field == "pull_number":
        return "Say the pull request number."
    if field == "to":
        return "Say recipient email addresses, separated by commas."
    if field == "subject":
        return "Say the email subject."
    if field == "draft_id":
        return "Say the Gmail draft id."
    if field == "reply_to_message_id":
        return "Say the Gmail message id to reply to."
    if field == "thread_id":
        return "Optionally say thread id, or say skip."
    return f"Say the {field}."


def _summary_from_catalog(entry: dict[str, Any], f: dict[str, str]) -> str:
    tpl = str(entry.get("summary_template") or "")
    body = f.get("body", "") or ""
    body_state = "empty" if not body.strip() else "provided"
    try:
        return tpl.format(
            repo=f.get("repo", ""),
            title=f.get("title", ""),
            body=body,
            body_state=body_state,
            base=f.get("base", ""),
            head=f.get("head", ""),
            pull_number=f.get("pull_number", ""),
            merge_method=f.get("merge_method", "squash"),
            to=f.get("to", ""),
            subject=f.get("subject", ""),
            reply_to_message_id=f.get("reply_to_message_id", ""),
            draft_id=f.get("draft_id", ""),
        )
    except Exception:
        return tpl or "This approval request."


def _confirm_summary(d: GovernedDraft) -> str:
    entry = _catalog_entry_for_voice(d.kind)
    if entry:
        return _summary_from_catalog(entry, d.fields)
    f = d.fields
    if d.kind == "gh_issue":
        return (
            f"GitHub issue in {f.get('repo', '')}, title {f.get('title', '')}. "
            f"Body {'empty' if not f.get('body', '').strip() else 'provided'}."
        )
    if d.kind == "gh_pr":
        return (
            f"GitHub draft pull request in {f.get('repo', '')}, base {f.get('base', '')}, "
            f"head {f.get('head', '')}, title {f.get('title', '')}."
        )
    if d.kind == "gh_merge":
        return (
            f"Merge GitHub pull request number {f.get('pull_number', '')} in {f.get('repo', '')} "
            f"using {f.get('merge_method', 'squash')}."
        )
    if d.kind == "gm_draft":
        return f"Gmail draft to {f.get('to', '')}, subject {f.get('subject', '')}."
    if d.kind == "gm_send":
        return f"Send Gmail draft {f.get('draft_id', '')}."
    if d.kind == "gm_reply":
        return f"Gmail reply draft on message {f.get('reply_to_message_id', '')}."
    return "This approval request."


async def _ensure_action_catalog(client: httpx.AsyncClient, base: str, api_key: str) -> None:
    global _catalog_cache, _catalog_load_failed
    if _catalog_cache is not None or _catalog_load_failed:
        return
    try:
        r = await client.get(
            f"{base}/api/v1/operator/action-catalog",
            headers={"x-api-key": api_key, "Accept": "application/json"},
            timeout=20.0,
        )
        r.raise_for_status()
        body = r.json()
        if isinstance(body, dict):
            _catalog_cache = body
        else:
            _catalog_load_failed = True
    except Exception as e:
        log.warning("action catalog: %s", e)
        _catalog_load_failed = True


def _next_field(kind: str, fields: dict[str, str]) -> str | None:
    for key in _field_order(kind):
        if key not in fields:
            return key
    return None


def _detect_start_kind(t: str) -> str | None:
    if RE_START_GH_ISSUE.search(t):
        return "gh_issue"
    if RE_START_GH_PR.search(t):
        return "gh_pr"
    if RE_INLINE_GH_MERGE.search(t) or RE_START_GH_MERGE.search(t):
        return "gh_merge"
    if RE_START_GM_DRAFT.search(t):
        return "gm_draft"
    if RE_INLINE_GM_SEND.search(t) or RE_START_GM_SEND.search(t):
        return "gm_send"
    if RE_START_GM_REPLY.search(t):
        return "gm_reply"
    return None


def _apply_inline_merge(t: str, draft: GovernedDraft) -> None:
    m = RE_INLINE_GH_MERGE.search(t)
    if m:
        draft.fields["pull_number"] = m.group(1)
        draft.fields["repo"] = m.group(2)


def _apply_inline_send(t: str, draft: GovernedDraft) -> None:
    m = RE_INLINE_GM_SEND.search(t)
    if m:
        draft.fields["draft_id"] = m.group(1)


async def _submit_draft(
    client: httpx.AsyncClient,
    base: str,
    api_key: str,
    draft: GovernedDraft,
) -> tuple[bool, str]:
    mid = draft.fields.get("mission_id") or ""
    if not mid:
        return False, "Internal error: missing mission."

    rb = _requested_by()
    via = "voice"
    headers = {"x-api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"}
    f = draft.fields

    try:
        if draft.kind == "gh_issue":
            body = {
                "repo": f["repo"],
                "title": f["title"],
                "body": f.get("body", ""),
                "requested_by": rb,
                "requested_via": via,
                "source_mission_id": mid,
            }
            labels_raw = f.get("labels", "").strip()
            if labels_raw:
                labels = [x.strip() for x in labels_raw.split(",") if x.strip()][:20]
                if labels:
                    body["labels"] = labels
            r = await client.post(
                f"{base}/api/v1/missions/{mid}/integrations/github/create-issue",
                json=body,
                headers=headers,
                timeout=60.0,
            )
        elif draft.kind == "gh_pr":
            r = await client.post(
                f"{base}/api/v1/missions/{mid}/integrations/github/create-pull-request",
                json={
                    "repo": f["repo"],
                    "base": f["base"],
                    "head": f["head"],
                    "title": f["title"],
                    "body": f.get("body", ""),
                    "draft": True,
                    "requested_by": rb,
                    "requested_via": via,
                    "source_mission_id": mid,
                },
                headers=headers,
                timeout=60.0,
            )
        elif draft.kind == "gh_merge":
            mm = (f.get("merge_method") or "squash").strip().lower()
            if mm not in ("merge", "squash", "rebase"):
                mm = "squash"
            merge_body: dict[str, Any] = {
                "repo": f["repo"],
                "pull_number": int(f["pull_number"]),
                "merge_method": mm,
                "requested_by": rb,
                "requested_via": via,
                "source_mission_id": mid,
            }
            sha = (f.get("expected_head_sha") or "").strip()
            if sha:
                merge_body["expected_head_sha"] = sha
            r = await client.post(
                f"{base}/api/v1/missions/{mid}/integrations/github/merge-pull-request",
                json=merge_body,
                headers=headers,
                timeout=90.0,
            )
        elif draft.kind == "gm_draft":
            to_list = [x.strip() for x in f["to"].split(",") if x.strip()]
            cc_list = [x.strip() for x in f.get("cc", "").split(",") if x.strip()]
            bcc_list = [x.strip() for x in f.get("bcc", "").split(",") if x.strip()]
            payload: dict[str, Any] = {
                "to": to_list,
                "subject": f["subject"],
                "body": f.get("body", ""),
                "requested_by": rb,
                "requested_via": via,
                "source_mission_id": mid,
            }
            if cc_list:
                payload["cc"] = cc_list
            if bcc_list:
                payload["bcc"] = bcc_list
            r = await client.post(
                f"{base}/api/v1/missions/{mid}/integrations/gmail/create-draft",
                json=payload,
                headers=headers,
                timeout=60.0,
            )
        elif draft.kind == "gm_send":
            r = await client.post(
                f"{base}/api/v1/missions/{mid}/integrations/gmail/send-draft",
                json={
                    "draft_id": f["draft_id"],
                    "requested_by": rb,
                    "requested_via": via,
                    "source_mission_id": mid,
                },
                headers=headers,
                timeout=60.0,
            )
        elif draft.kind == "gm_reply":
            payload = {
                "reply_to_message_id": f["reply_to_message_id"],
                "body": f.get("body", ""),
                "requested_by": rb,
                "requested_via": via,
                "source_mission_id": mid,
            }
            tid = f.get("thread_id", "").strip()
            if tid and tid.lower() != "skip":
                payload["thread_id"] = tid
            r = await client.post(
                f"{base}/api/v1/missions/{mid}/integrations/gmail/create-reply-draft",
                json=payload,
                headers=headers,
                timeout=60.0,
            )
        else:
            return False, "Unknown action kind."

        if r.status_code >= 400:
            return False, _error_detail(r)

        data = r.json()
        aid = data.get("id") if isinstance(data, dict) else None
        short = _short_id(str(aid)) if aid else "unknown"
        summary = _confirm_summary(draft)
        msg = (
            f"Your governed action request is pending approval. {summary} "
            f"Short id {short}. Review it in Command Center under Approvals, "
            f"or say what needs my approval to hear the queue."
        )
        return True, msg
    except Exception as e:
        log.warning("submit draft: %s", e)
        return False, f"Request failed: {e!s}"[:400]


async def try_handle_governed_action_voice(
    text: str,
    ws_key: int,
    *,
    control_plane_url: str,
    api_key: str,
) -> str | None:
    """
    If handled, return spoken reply. None = fall through to next handler.
    """
    t = _norm(text)
    if not t:
        return None

    if not api_key.strip():
        # Still allow cancel / vague messaging
        if _get_draft(ws_key) and RE_CANCEL.search(t):
            _clear_draft(ws_key)
            return "Cancelled the action request."
        if _detect_start_kind(t):
            return "Control plane API key is not configured; I cannot create approval requests by voice."
        return None

    base = control_plane_url.rstrip("/")
    draft = _get_draft(ws_key)

    # --- Cancel anytime draft exists ---
    if draft and RE_CANCEL.search(t):
        _clear_draft(ws_key)
        return "Cancelled the action request."

    if draft and _detect_start_kind(t):
        return "Finish or cancel the current action request first. Say cancel that to abort."

    async with httpx.AsyncClient() as client:
        await _ensure_action_catalog(client, base, api_key)

        # --- Active draft ---
        if draft:
            if draft.step == "confirm":
                if RE_VAGUE_DO.match(t):
                    return (
                        "Say confirm to submit this approval request. "
                        "I do not act on vague phrases like send it or merge it."
                    )
                if RE_CONFIRM.match(t):
                    ok, msg = await _submit_draft(client, base, api_key, draft)
                    _clear_draft(ws_key)
                    return msg if ok else f"I did not submit that. {msg}"
                if RE_CANCEL.search(t):
                    _clear_draft(ws_key)
                    return "Cancelled. Nothing was submitted."
                return (
                    "Say confirm to submit this approval request, or cancel that to discard it. "
                    "I need an explicit confirm, not a vague go-ahead."
                )

            # collect
            if RE_VAGUE_DO.match(t):
                return (
                    "I did not submit anything. Use explicit answers for each field, "
                    "or say cancel that to abort."
                )

            nf = _next_field(draft.kind, draft.fields)
            if nf is None:
                draft.step = "confirm"
                return (
                    f"Ready to submit. {_confirm_summary(draft)} "
                    f"Say confirm to create the approval request, or cancel that to discard."
                )

            # Fill current field from utterance
            if nf == "mission_id":
                mid, err = await _resolve_mission_id(text, client, base, api_key, ws_key)
                if err:
                    return err
                if mid:
                    draft.fields["mission_id"] = mid
                    nn = _next_field(draft.kind, draft.fields)
                    if nn:
                        return f"Using mission {_short_id(mid)}. {_prompt_for(draft.kind, nn)}"
                    draft.step = "confirm"
                    return (
                        f"Ready to submit. {_confirm_summary(draft)} "
                        f"Say confirm to create the approval request."
                    )
                return (
                    err
                    or "I did not understand a mission id. Say last for the previous voice mission, "
                    "or the full mission uuid, or at least eight hex characters of the id."
                )

            val = text.strip()
            low = _norm(val)

            if nf == "body" and low in ("skip", "skip body", "empty", "no body", "nothing"):
                draft.fields["body"] = ""
            elif nf == "thread_id" and low in ("skip", "none", "no"):
                draft.fields["thread_id"] = ""
            elif nf == "labels":
                low = _norm(val)
                if low in ("skip", "none", "no", "no labels"):
                    draft.fields["labels"] = ""
                else:
                    draft.fields["labels"] = val.strip()
            elif nf == "merge_method":
                low = _norm(val)
                if low in ("skip", "default", ""):
                    draft.fields["merge_method"] = "squash"
                elif "squash" in low:
                    draft.fields["merge_method"] = "squash"
                elif "rebase" in low:
                    draft.fields["merge_method"] = "rebase"
                elif "merge" in low:
                    draft.fields["merge_method"] = "merge"
                else:
                    return "Say merge method squash, merge, or rebase. Or say skip for squash."
            elif nf == "expected_head_sha":
                low = _norm(val)
                if low in ("skip", "none", "no", ""):
                    draft.fields["expected_head_sha"] = ""
                else:
                    draft.fields["expected_head_sha"] = val.strip()
            elif nf in ("cc", "bcc"):
                low = _norm(val)
                if low in ("skip", "none", "no"):
                    draft.fields[nf] = ""
                else:
                    parts = [x.strip() for x in val.split(",") if x.strip()]
                    draft.fields[nf] = ",".join(parts)
            elif nf == "repo":
                if not _REPO_RE.match(val.strip()):
                    return "Repository must look like owner slash name. Try again."
                draft.fields["repo"] = val.strip()
            elif nf == "pull_number":
                digits = re.sub(r"[^\d]", "", val)
                if not digits or int(digits) < 1:
                    return "Say a positive pull request number."
                draft.fields["pull_number"] = digits
            elif nf == "to":
                parts = [x.strip() for x in val.split(",") if x.strip()]
                if not parts:
                    return "I need at least one email address."
                draft.fields["to"] = ",".join(parts)
            elif nf == "title":
                if not val.strip():
                    return "I need a non-empty title."
                draft.fields["title"] = val.strip()
            elif nf == "subject":
                if draft.kind == "gm_reply":
                    s_low = _norm(val)
                    if s_low in ("skip", "none", "no"):
                        draft.fields["subject"] = ""
                    else:
                        draft.fields["subject"] = val.strip()
                elif not val.strip():
                    return "I need a non-empty subject."
                else:
                    draft.fields["subject"] = val.strip()
            elif nf == "reply_to_message_id":
                if not val.strip():
                    return "I need the Gmail message id to reply to."
                draft.fields["reply_to_message_id"] = val.strip()
            elif nf == "draft_id":
                if not val.strip():
                    return "I need the draft id."
                draft.fields["draft_id"] = val.strip()
            elif nf in ("base", "head"):
                if not val.strip():
                    return f"I need a non-empty {nf} branch name."
                draft.fields[nf] = val.strip()
            else:
                draft.fields[nf] = val.strip()

            nn = _next_field(draft.kind, draft.fields)
            if nn:
                return _prompt_for(draft.kind, nn)
            draft.step = "confirm"
            return (
                f"Ready to submit. {_confirm_summary(draft)} "
                f"Say confirm to create the approval request, or cancel that to discard."
            )

        # --- No draft: start? ---
        kind = _detect_start_kind(t)
        if not kind:
            return None

        new_d = GovernedDraft(kind=kind)
        if kind == "gh_merge":
            _apply_inline_merge(t, new_d)
        if kind == "gm_send":
            _apply_inline_send(t, new_d)

        _drafts[ws_key] = new_d
        nf = _next_field(kind, new_d.fields)
        if nf:
            entry = _catalog_entry_for_voice(kind)
            intro = None
            if entry and isinstance(entry.get("voice_intro"), str) and entry["voice_intro"].strip():
                intro = entry["voice_intro"].strip()
            if not intro:
                intro = {
                    "gh_issue": "Starting a GitHub issue approval request.",
                    "gh_pr": "Starting a GitHub draft pull request approval request.",
                    "gh_merge": "Starting a GitHub merge approval request.",
                    "gm_draft": "Starting a Gmail draft approval request.",
                    "gm_send": "Starting a Gmail send-draft approval request.",
                    "gm_reply": "Starting a Gmail reply draft approval request.",
                }.get(kind, "Starting an approval request.")
            return f"{intro} {_prompt_for(kind, nf)}"
        new_d.step = "confirm"
        return (
            f"Ready to submit. {_confirm_summary(new_d)} "
            f"Say confirm to create the approval request."
        )


