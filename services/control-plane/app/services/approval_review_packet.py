"""Approval Review Packet v1 — normalize command_text into inspectable operator packets."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import Approval
from app.models.mission_event import MissionEvent
from app.repositories.approval_repo import ApprovalRepository
from app.repositories.mission_event_repo import MissionEventRepository
from app.repositories.mission_repo import MissionRepository
from app.repositories.receipt_repo import ReceiptRepository
from app.schemas.approval_bundle import (
    ApprovalBundleResponse,
    ApprovalContextBlock,
    ApprovalReviewPacket,
    BundleDataQuality,
    MissionEventSnippet,
    PacketField,
    ReceiptSnippet,
)
from app.schemas.approvals import ApprovalRead
from app.schemas.github_issue import GitHubCreateIssueContract
from app.schemas.github_pr import GitHubCreatePullRequestContract
from app.schemas.github_pr_merge import GitHubMergePullRequestContract
from app.schemas.gmail_draft import (
    GmailCreateDraftContract,
    GmailCreateReplyDraftContract,
    GmailSendDraftContract,
)
from app.schemas.missions import MissionRead


def _truncate(s: str, n: int = 400) -> str:
    t = (s or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _json_try(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        o = json.loads(raw)
        return o if isinstance(o, dict) else None
    except json.JSONDecodeError:
        return None


def _identity_bearing(risk_class: str, action_type: str) -> bool:
    """Red risk or external integration surface (GitHub / Gmail)."""
    if str(risk_class).lower() == "red":
        return True
    if action_type.startswith("github_") or action_type.startswith("gmail_"):
        return True
    return False


def _safe_json_preview(v: Any, max_len: int = 120) -> str:
    try:
        s = json.dumps(v, default=str, ensure_ascii=False)
    except TypeError:
        s = repr(v)
    return _truncate(s, max_len)


def build_review_packet(
    *,
    action_type: str,
    command_text: str | None,
    reason: str | None,
    risk_class: str,
) -> ApprovalReviewPacket:
    """Pure: normalize command_text + metadata into a review packet."""
    ib = _identity_bearing(risk_class, action_type)
    data = _json_try(command_text)

    if data is None:
        if not (command_text and str(command_text).strip()):
            return ApprovalReviewPacket(
                kind="generic",
                action_type=action_type,
                headline=action_type,
                subheadline="No structured command payload stored.",
                operator_effect="Depends on mission execution pipeline when approved.",
                identity_bearing=ib,
                fields=[],
                brief_summary=reason or f"Approval for {action_type}.",
                spoken_summary=reason or f"Approval requested: {action_type}.",
                preflight_available=False,
                parse_ok=True,
                parse_note="No command_text JSON — generic approval.",
            )
        return ApprovalReviewPacket(
            kind="parse_error",
            action_type=action_type,
            headline=action_type,
            subheadline="command_text is not valid JSON",
            identity_bearing=ib,
            fields=[PacketField(label="Raw preview", value=_truncate(str(command_text), 500))],
            brief_summary=reason or "Structured payload could not be parsed.",
            spoken_summary=reason or f"Approval {action_type}: payload could not be parsed as JSON.",
            preflight_available=False,
            parse_ok=False,
            parse_note="command_text is present but is not valid JSON.",
        )

    builders = {
        "github_create_issue": _packet_github_issue,
        "github_create_pull_request": _packet_github_pr,
        "github_merge_pull_request": _packet_github_merge,
        "gmail_create_draft": _packet_gmail_draft,
        "gmail_create_reply_draft": _packet_gmail_reply_draft,
        "gmail_send_draft": _packet_gmail_send,
    }
    fn = builders.get(action_type)
    if fn is None:
        return _packet_generic(action_type, data, reason, ib)

    try:
        return fn(data, reason, ib)
    except Exception as e:
        return ApprovalReviewPacket(
            kind="parse_error",
            action_type=action_type,
            headline=action_type,
            subheadline="Structured payload did not match expected contract",
            identity_bearing=ib,
            fields=[PacketField(label="Parse detail", value=_truncate(str(e), 300))],
            brief_summary=reason or "Payload could not be normalized.",
            spoken_summary=reason or f"Approval {action_type}: contract validation failed.",
            preflight_available=False,
            parse_ok=False,
            parse_note=str(e)[:500],
        )


def _packet_github_issue(
    data: dict[str, Any], reason: str | None, ib: bool
) -> ApprovalReviewPacket:
    c = GitHubCreateIssueContract.model_validate(data)
    fields = [
        PacketField(label="Repository", value=c.repo),
        PacketField(label="Title", value=c.title),
        PacketField(label="Body", value=_truncate(c.body, 400) if c.body else "(empty)"),
    ]
    if c.labels:
        fields.append(PacketField(label="Labels", value=", ".join(c.labels)))
    if c.assignees:
        fields.append(PacketField(label="Assignees", value=", ".join(c.assignees)))
    spoken = f"Create GitHub issue in {c.repo} titled {c.title}."
    return ApprovalReviewPacket(
        kind="typed",
        action_type="github_create_issue",
        headline="Create GitHub issue",
        subheadline=c.repo,
        action_kind="github_issue",
        operator_effect="Opens a new issue in the repository via GitHub API.",
        target_summary=f"{c.repo} — {c.title}",
        identity_bearing=ib,
        fields=fields,
        brief_summary=f"Issue in {c.repo}: {c.title}",
        spoken_summary=spoken,
        preflight_available=False,
        parse_ok=True,
    )


def _packet_github_pr(data: dict[str, Any], reason: str | None, ib: bool) -> ApprovalReviewPacket:
    c = GitHubCreatePullRequestContract.model_validate(data)
    draft_lbl = "draft " if c.draft else ""
    fields = [
        PacketField(label="Repository", value=c.repo),
        PacketField(label="Base", value=c.base),
        PacketField(label="Head", value=c.head),
        PacketField(label="Title", value=c.title),
        PacketField(label="Draft", value="yes" if c.draft else "no"),
    ]
    if c.body:
        fields.append(PacketField(label="Description", value=_truncate(c.body, 400)))
    spoken = (
        f"Create GitHub {draft_lbl}pull request in {c.repo} from {c.head} into {c.base}: {c.title}."
    )
    return ApprovalReviewPacket(
        kind="typed",
        action_type="github_create_pull_request",
        headline=f"Create GitHub {'draft ' if c.draft else ''}pull request",
        subheadline=c.repo,
        action_kind="github_pull_request",
        operator_effect="Creates a pull request from head into base.",
        target_summary=f"{c.repo} {c.head}→{c.base}",
        identity_bearing=ib,
        fields=fields,
        brief_summary=f"PR {c.repo}: {c.head}→{c.base} — {c.title}",
        spoken_summary=spoken,
        preflight_available=False,
        parse_ok=True,
    )


def _packet_github_merge(data: dict[str, Any], reason: str | None, ib: bool) -> ApprovalReviewPacket:
    c = GitHubMergePullRequestContract.model_validate(data)
    fields = [
        PacketField(label="Repository", value=c.repo),
        PacketField(label="Pull request", value=f"#{c.pull_number}"),
        PacketField(label="Merge method", value=c.merge_method),
    ]
    if c.commit_title:
        fields.append(PacketField(label="Commit title", value=c.commit_title))
    if c.commit_message:
        fields.append(PacketField(label="Commit message", value=_truncate(c.commit_message, 300)))
    if c.expected_head_sha:
        fields.append(PacketField(label="Expected head SHA", value=c.expected_head_sha))
    spoken = (
        f"{c.merge_method} merge GitHub pull request number {c.pull_number} in {c.repo}. "
        "Preflight snapshot may appear below when recorded on the mission timeline."
    )
    return ApprovalReviewPacket(
        kind="typed",
        action_type="github_merge_pull_request",
        headline=f"Merge GitHub PR #{c.pull_number}",
        subheadline=c.repo,
        action_kind="github_pr_merge",
        operator_effect="Merges the open pull request using the chosen merge method.",
        target_summary=f"{c.repo} PR #{c.pull_number}",
        identity_bearing=ib,
        fields=fields,
        brief_summary=f"{c.merge_method} merge PR #{c.pull_number} in {c.repo}",
        spoken_summary=spoken,
        preflight_summary=None,
        preflight_available=False,
        parse_ok=True,
        parse_note=None,
    )


def _packet_gmail_draft(data: dict[str, Any], reason: str | None, ib: bool) -> ApprovalReviewPacket:
    c = GmailCreateDraftContract.model_validate(data)
    to_s = ", ".join(str(x) for x in c.to[:8])
    fields = [
        PacketField(label="To", value=to_s),
        PacketField(label="Subject", value=c.subject),
        PacketField(label="Body", value=_truncate(c.body, 400) if c.body else "(empty)"),
    ]
    if c.cc:
        fields.append(PacketField(label="Cc", value=", ".join(str(x) for x in c.cc[:8])))
    if c.bcc:
        fields.append(PacketField(label="Bcc", value=", ".join(str(x) for x in c.bcc[:8])))
    spoken = f"Create Gmail draft to {to_s} with subject {c.subject}."
    return ApprovalReviewPacket(
        kind="typed",
        action_type="gmail_create_draft",
        headline="Create Gmail draft",
        subheadline=c.subject,
        action_kind="gmail_draft",
        operator_effect="Creates a draft in Gmail; does not send.",
        target_summary=to_s,
        identity_bearing=ib,
        fields=fields,
        brief_summary=f"Draft to {to_s}: {c.subject}",
        spoken_summary=spoken,
        preflight_available=False,
        parse_ok=True,
    )


def _packet_gmail_reply_draft(
    data: dict[str, Any], reason: str | None, ib: bool
) -> ApprovalReviewPacket:
    c = GmailCreateReplyDraftContract.model_validate(data)
    fields = [
        PacketField(label="Reply to message id", value=c.reply_to_message_id),
    ]
    if c.thread_id:
        fields.append(PacketField(label="Thread id (hint)", value=c.thread_id))
    if c.to_preview:
        fields.append(PacketField(label="To (preview)", value=c.to_preview))
    subj = (c.subject or "").strip() or "(default Re: … from thread)"
    fields.append(PacketField(label="Subject", value=subj))
    fields.append(PacketField(label="Body", value=_truncate(c.body, 400) if c.body else "(empty)"))
    if c.cc:
        fields.append(PacketField(label="Cc", value=", ".join(str(x) for x in c.cc[:8])))
    if c.bcc:
        fields.append(PacketField(label="Bcc", value=", ".join(str(x) for x in c.bcc[:8])))
    tp = c.to_preview or "recipient"
    spoken = (
        f"Create Gmail reply draft in thread to {tp}, replying to message {c.reply_to_message_id}, "
        f"subject {subj}."
    )
    return ApprovalReviewPacket(
        kind="typed",
        action_type="gmail_create_reply_draft",
        headline="Create Gmail reply draft",
        subheadline=c.reply_to_message_id,
        action_kind="gmail_reply_draft",
        operator_effect="Creates a draft reply in the existing Gmail thread; does not send.",
        target_summary=f"msg {c.reply_to_message_id} → {tp}",
        identity_bearing=ib,
        fields=fields,
        brief_summary=f"Reply draft to {tp} (message {c.reply_to_message_id})",
        spoken_summary=spoken,
        preflight_available=False,
        parse_ok=True,
    )


def _packet_gmail_send(data: dict[str, Any], reason: str | None, ib: bool) -> ApprovalReviewPacket:
    c = GmailSendDraftContract.model_validate(data)
    fields = [PacketField(label="Draft id", value=c.draft_id)]
    if c.to_preview:
        fields.append(PacketField(label="To (preview)", value=c.to_preview))
    if c.subject:
        fields.append(PacketField(label="Subject (preview)", value=c.subject))
    if c.message_id:
        fields.append(PacketField(label="Message id hint", value=c.message_id))
    tp = c.to_preview or ""
    sub = c.subject or ""
    spoken = (
        f"Send Gmail draft {c.draft_id}"
        + (f" to {tp}" if tp else "")
        + (f" with subject {sub}" if sub else "")
        + "."
    )
    return ApprovalReviewPacket(
        kind="typed",
        action_type="gmail_send_draft",
        headline="Send Gmail draft",
        subheadline=c.draft_id,
        action_kind="gmail_send",
        operator_effect="Sends the existing draft via Gmail API after approval.",
        target_summary=c.draft_id,
        identity_bearing=ib,
        fields=fields,
        brief_summary=f"Send draft {c.draft_id}" + (f" — {sub}" if sub else ""),
        spoken_summary=spoken,
        preflight_available=False,
        parse_ok=True,
    )


def _packet_generic(
    action_type: str, data: dict[str, Any], reason: str | None, ib: bool
) -> ApprovalReviewPacket:
    keys = list(data.keys())[:12]
    fields = [PacketField(label=k, value=_safe_json_preview(data[k])) for k in keys]
    return ApprovalReviewPacket(
        kind="generic",
        action_type=action_type,
        headline=action_type,
        subheadline="Unknown or non-integrated action type",
        operator_effect="Execution depends on configured handler for this action type.",
        identity_bearing=ib,
        fields=fields,
        brief_summary=reason or f"Structured payload for {action_type}.",
        spoken_summary=reason or f"Approval for {action_type}.",
        preflight_available=False,
        parse_ok=True,
        parse_note="action_type has no dedicated packet builder — showing compact key/value preview only.",
    )


def _event_summary(ev: MissionEvent) -> str:
    et = ev.event_type
    p = ev.payload or {}
    if et == "integration_action_requested":
        prov = str(p.get("provider") or "")
        act = str(p.get("action") or "")
        return f"{et}: {prov} {act}".strip()
    if et == "approval_requested":
        return f"approval_requested: {p.get('action_type', '')}"
    if et == "receipt_recorded":
        return f"receipt: {p.get('receipt_type', '')}"
    return et


def _extract_merge_preflight_event(
    events: list[MissionEvent], approval_id: UUID
) -> tuple[dict[str, Any] | None, bool]:
    """Return (preflight dict, saw matching integration_action_requested for this approval)."""
    aid = str(approval_id)
    for ev in reversed(events):
        if ev.event_type != "integration_action_requested":
            continue
        p = ev.payload or {}
        if str(p.get("approval_id") or "") != aid:
            continue
        if str(p.get("action") or "") != "merge_pull_request":
            continue
        pf = p.get("preflight")
        if isinstance(pf, dict):
            return pf, True
        return None, True
    return None, False


def _preflight_merge_line(pf: dict[str, Any]) -> str:
    parts: list[str] = []
    for k in (
        "pr_title",
        "base_ref",
        "head_ref",
        "head_sha",
        "mergeable",
        "mergeable_state",
        "checks_summary",
        "draft",
        "html_url",
    ):
        if pf.get(k) in (None, "", []):
            continue
        parts.append(f"{k}: {pf[k]}")
    return " · ".join(parts)


def _preflight_merge_extra_fields(pf: dict[str, Any]) -> list[PacketField]:
    out: list[PacketField] = []
    if pf.get("pr_title"):
        out.append(PacketField(label="PR title (preflight)", value=_truncate(str(pf["pr_title"]), 200)))
    if pf.get("base_ref"):
        out.append(PacketField(label="Base (preflight)", value=str(pf["base_ref"])))
    if pf.get("head_ref"):
        out.append(PacketField(label="Head (preflight)", value=str(pf["head_ref"])))
    if pf.get("head_sha"):
        out.append(PacketField(label="Head SHA (preflight)", value=str(pf["head_sha"])[:48]))
    if "mergeable" in pf and pf["mergeable"] is not None:
        out.append(PacketField(label="Mergeable (preflight)", value=str(pf["mergeable"])))
    if pf.get("mergeable_state"):
        out.append(PacketField(label="Mergeable state", value=str(pf["mergeable_state"])))
    if pf.get("checks_summary"):
        out.append(PacketField(label="Checks (preflight)", value=_truncate(str(pf["checks_summary"]), 240)))
    if pf.get("draft") is not None:
        out.append(PacketField(label="Draft (preflight)", value="yes" if pf["draft"] else "no"))
    if pf.get("html_url"):
        out.append(PacketField(label="PR link", value=str(pf["html_url"])[:512]))
    return out


def _enrich_merge_packet_with_preflight(
    packet: ApprovalReviewPacket,
    pf: dict[str, Any] | None,
    saw_event: bool,
) -> ApprovalReviewPacket:
    if packet.action_type != "github_merge_pull_request":
        return packet
    line = _preflight_merge_line(pf) if pf else ""
    extra = _preflight_merge_extra_fields(pf) if pf else []
    new_fields = list(packet.fields)
    insert_at = min(3, len(new_fields))
    for i, f in enumerate(extra):
        new_fields.insert(insert_at + i, f)

    spoken = packet.spoken_summary
    brief = packet.brief_summary
    if pf:
        repo = next((f.value for f in packet.fields if f.label == "Repository"), "")
        pr_num = next((f.value for f in packet.fields if f.label == "Pull request"), "")
        mm = next((f.value for f in packet.fields if f.label == "Merge method"), "merge")
        br, hr = pf.get("base_ref"), pf.get("head_ref")
        if br and hr:
            spoken = f"{mm} merge GitHub pull request {pr_num} in {repo}: {hr} into {br}."
        if pf.get("checks_summary"):
            spoken = spoken.rstrip(".") + f" Preflight checks: {pf['checks_summary']}."
        elif pf.get("mergeable_state"):
            spoken = spoken.rstrip(".") + f" Mergeable state: {pf['mergeable_state']}."
        if pf.get("pr_title"):
            brief = f"{packet.brief_summary} — {pf['pr_title']}"[:400]

    return packet.model_copy(
        update={
            "fields": new_fields,
            "preflight_summary": line or None,
            "preflight_available": bool(saw_event and pf),
            "spoken_summary": spoken,
            "brief_summary": brief,
            "parse_note": None if (saw_event and pf) else packet.parse_note,
        }
    )


async def build_approval_bundle_from_row(
    session: AsyncSession,
    approval_row: Approval,
) -> ApprovalBundleResponse:
    missions = MissionRepository(session)
    mission_row = await missions.get_by_id(approval_row.mission_id)
    mission_read = MissionRead.model_validate(mission_row) if mission_row else None

    now = datetime.now(UTC)
    created = approval_row.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    age_s = (now - created).total_seconds()

    approval_read = ApprovalRead.model_validate(approval_row)

    packet = build_review_packet(
        action_type=approval_row.action_type,
        command_text=approval_row.command_text,
        reason=approval_row.reason,
        risk_class=approval_row.risk_class,
    )

    events = await MissionEventRepository.list_by_mission(session, approval_row.mission_id)
    notes: list[str] = []

    pf_dict: dict[str, Any] | None
    saw_merge_ev: bool
    pf_dict, saw_merge_ev = _extract_merge_preflight_event(events, approval_row.id)
    if approval_row.action_type == "github_merge_pull_request":
        packet = _enrich_merge_packet_with_preflight(packet, pf_dict, saw_merge_ev)
        if not saw_merge_ev:
            notes.append(
                "No integration_action_requested merge preflight event found for this approval on the mission timeline."
            )
        elif not pf_dict:
            notes.append(
                "Merge approval event exists but preflight payload was empty — GitHub state unknown from timeline."
            )

    recent_ev = events[-15:] if len(events) > 15 else events
    event_snips: list[MissionEventSnippet] = []
    for ev in recent_ev:
        event_snips.append(
            MissionEventSnippet(
                id=ev.id,
                event_type=ev.event_type,
                created_at=ev.created_at,
                summary=_event_summary(ev)[:240],
            )
        )

    receipts = await ReceiptRepository.list_by_mission(session, approval_row.mission_id)
    recent_rc = receipts[-8:] if len(receipts) > 8 else receipts
    rc_snips = [
        ReceiptSnippet(
            id=r.id,
            receipt_type=r.receipt_type,
            created_at=r.created_at,
            summary=r.summary,
        )
        for r in recent_rc
    ]

    mid = approval_row.mission_id
    ctx = ApprovalContextBlock(
        requested_by=approval_row.requested_by,
        requested_via=approval_row.requested_via,
        risk_class=approval_row.risk_class,
        created_at=approval_row.created_at,
        age_seconds=age_s,
        mission_id=mid,
        mission_title=mission_row.title if mission_row else None,
        mission_status=mission_row.status if mission_row else None,
        mission_link=f"/missions/{mid}",
        identity_bearing=_identity_bearing(approval_row.risk_class, approval_row.action_type),
        reason_line=approval_row.reason,
    )

    dq = BundleDataQuality(
        direct_from_store=[
            "approval row fields (mission_id, action_type, risk_class, reason, command_text, timestamps)",
            "mission row when present",
            "mission_events and receipts for this mission (bounded lists)",
        ],
        derived=[
            "Review packet fields from command_text JSON via workflow contracts",
            "Merge preflight rows from integration_action_requested when approval_id matches",
            "Age in seconds from server UTC clock",
        ],
        notes=[
            "Secrets are not returned; values are contract-shaped or truncated previews only.",
            "If a workflow adds new fields, extend the packet builder for that action_type.",
        ],
    )

    return ApprovalBundleResponse(
        generated_at=now,
        approval=approval_read,
        mission=mission_read,
        context=ctx,
        packet=packet,
        recent_events=event_snips,
        related_receipts=rc_snips,
        data_quality=dq,
        notes=notes,
    )


async def build_approval_bundle(session: AsyncSession, approval_id: UUID) -> ApprovalBundleResponse | None:
    """Load approval by id; returns None if missing (caller maps to HTTP 404)."""
    row = await ApprovalRepository.get(session, approval_id)
    if row is None:
        return None
    return await build_approval_bundle_from_row(session, row)
