"""Governed GitHub PR merge: preflight + approval + merge only."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.integrations.github_adapter import (
    get_commit_check_runs_json,
    get_pull_request_json,
    merge_pull_request,
)
from app.models.approval import Approval
from app.repositories.mission_event_repo import MissionEventRepository
from app.repositories.mission_repo import MissionRepository
from app.schemas.github_pr_merge import (
    GitHubMergePullRequestContract,
    GitHubMergePullRequestRequest,
    GitHubPullRequestMergeResult,
)
from app.services.receipt_service import ReceiptService

log = get_logger(__name__)

ACTION_TYPE = "github_merge_pull_request"
RISK_CLASS = "red"

_BAD_MERGEABLE_STATES = frozenset({"dirty", "blocked", "unknown"})
_ALLOWED_MERGEABLE_STATES = frozenset({"", "clean", "behind"})
_BAD_CHECK_CONCLUSIONS = frozenset({"failure", "cancelled", "timed_out", "action_required", "stale"})


def _head_sha(pr: dict[str, Any]) -> str | None:
    h = pr.get("head")
    if isinstance(h, dict):
        s = h.get("sha")
        return str(s) if s else None
    return None


def _base_ref(pr: dict[str, Any]) -> str | None:
    b = pr.get("base")
    if isinstance(b, dict):
        r = b.get("ref")
        return str(r) if r else None
    return None


def _head_ref(pr: dict[str, Any]) -> str | None:
    h = pr.get("head")
    if isinstance(h, dict):
        r = h.get("ref")
        return str(r) if r else None
    return None


def _checks_summary_from_runs(data: dict[str, Any]) -> str:
    runs = data.get("check_runs") or []
    if not isinstance(runs, list):
        return "check_runs unavailable"
    n = len(runs)
    if n == 0:
        return "no check runs"
    ok = sum(
        1
        for x in runs
        if isinstance(x, dict) and str(x.get("conclusion") or "") == "success"
    )
    fail = sum(
        1
        for x in runs
        if isinstance(x, dict) and str(x.get("conclusion") or "") in _BAD_CHECK_CONCLUSIONS
    )
    pend = sum(
        1
        for x in runs
        if isinstance(x, dict) and str(x.get("status") or "") in ("queued", "in_progress")
    )
    return f"{n} runs: {ok} ok, {fail} failed/problem, {pend} pending"


async def preflight_merge(
    *,
    token: str,
    contract: GitHubMergePullRequestContract,
) -> tuple[bool, str | None, str | None, dict[str, Any]]:
    """
    Returns (ok, error_code, error_message, snapshot).
    Snapshot is safe, compact PR + checks summary for approval copy and events.
    """
    pr, status, err = await get_pull_request_json(
        token=token, repo=contract.repo, pull_number=contract.pull_number
    )
    snap: dict[str, Any] = {
        "repo": contract.repo,
        "pull_number": contract.pull_number,
        "merge_method": contract.merge_method,
    }

    if pr is None:
        code = "pr_not_found" if status == 404 else f"github_http_{status}" if status else "provider_http_error"
        return False, code, err or "Could not load pull request.", snap

    title = str(pr.get("title") or "")
    html_url = str(pr.get("html_url") or "")
    state = str(pr.get("state") or "")
    draft = pr.get("draft") is True
    mergeable = pr.get("mergeable")
    mstate = str(pr.get("mergeable_state") or "")
    head_sha = _head_sha(pr)

    snap.update(
        {
            "pr_title": title,
            "base_ref": _base_ref(pr),
            "head_ref": _head_ref(pr),
            "head_sha": head_sha,
            "state": state,
            "draft": draft,
            "mergeable": mergeable,
            "mergeable_state": mstate,
            "html_url": html_url,
        }
    )

    if state != "open":
        return False, "pr_not_open", f"PR is not open (state={state}).", snap
    if draft:
        return False, "pr_is_draft", "Draft pull requests cannot be merged via this workflow.", snap

    if contract.expected_head_sha and head_sha:
        exp = contract.expected_head_sha.strip().lower()
        if not head_sha.lower().startswith(exp.lower()) and head_sha.lower() != exp.lower():
            return False, "pr_head_sha_mismatch", "PR head SHA does not match expected_head_sha.", snap

    if mergeable is None:
        return False, "pr_mergeability_unknown", "GitHub has not computed mergeability yet; retry later.", snap
    if mergeable is False:
        return False, "pr_not_mergeable", "GitHub reports the PR is not mergeable.", snap

    if mstate in _BAD_MERGEABLE_STATES:
        return False, "pr_not_mergeable", f"mergeable_state={mstate} — cannot merge conservatively.", snap
    if mstate == "unstable":
        return False, "checks_failed", "mergeable_state=unstable (failing checks or conflicts).", snap
    if mstate and mstate not in _ALLOWED_MERGEABLE_STATES:
        return False, "pr_not_mergeable", f"mergeable_state={mstate} not allowed for v1 merge.", snap

    if head_sha is None:
        return False, "pr_head_missing", "Could not read PR head SHA for checks.", snap

    cr, cr_status, cr_err = await get_commit_check_runs_json(
        token=token, repo=contract.repo, head_sha=head_sha
    )
    if cr is None:
        return False, "checks_unavailable", cr_err or "Could not read check runs for head commit.", snap

    snap["checks_summary"] = _checks_summary_from_runs(cr)
    runs = cr.get("check_runs") or []
    if isinstance(runs, list) and len(runs) > 0:
        for x in runs:
            if not isinstance(x, dict):
                continue
            st = str(x.get("status") or "")
            if st in ("queued", "in_progress"):
                return False, "checks_pending", "Check runs still pending; wait for CI to finish.", snap
            con = str(x.get("conclusion") or "")
            if con in _BAD_CHECK_CONCLUSIONS:
                name = str(x.get("name") or "check")
                return False, "checks_failed", f"Check {name!r} conclusion={con}.", snap
    # Empty check_runs: no GitHub Checks on this commit — rely on mergeable + mergeable_state only.

    return True, None, None, snap


def human_reason(contract: GitHubMergePullRequestContract, snapshot: dict[str, Any]) -> str:
    method = contract.merge_method
    base = snapshot.get("base_ref") or "?"
    title = snapshot.get("pr_title") or ""
    tail = f" — {title}" if title else ""
    checks = snapshot.get("checks_summary")
    cs = f" · {checks}" if checks else ""
    return (
        f"{method} merge GitHub PR #{contract.pull_number} in {contract.repo} into {base}{tail}{cs}"
    )


def contract_to_command_text(contract: GitHubMergePullRequestContract) -> str:
    return contract.model_dump_json()


async def submit_merge_pull_request(
    session: AsyncSession,
    *,
    mission_id: UUID,
    body: GitHubMergePullRequestRequest,
) -> Approval:
    from fastapi import HTTPException, status

    from app.services.approval_service import ApprovalService

    contract = GitHubMergePullRequestContract.model_validate(
        body.model_dump(exclude={"requested_by", "requested_via"})
    )
    missions = MissionRepository(session)
    mission = await missions.get_by_id(mission_id)
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")

    settings = get_settings()
    token = (settings.JARVIS_GITHUB_TOKEN or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="JARVIS_GITHUB_TOKEN is required for merge preflight on the control plane.",
        )

    ok, err_code, err_msg, snapshot = await preflight_merge(token=token, contract=contract)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": err_code, "message": err_msg or "Preflight failed"},
        )

    svc = ApprovalService(session)
    approval = await svc.request_approval(
        mission_id=mission_id,
        action_type=ACTION_TYPE,
        risk_class=RISK_CLASS,
        reason=human_reason(contract, snapshot),
        requested_by=body.requested_by,
        requested_via=body.requested_via,
        command_text=contract_to_command_text(contract),
    )

    safe_payload: dict[str, Any] = {
        "provider": contract.provider,
        "action": contract.action,
        "repo": contract.repo,
        "pull_number": contract.pull_number,
        "merge_method": contract.merge_method,
        "approval_id": str(approval.id),
        "preflight": {
            "pr_title": snapshot.get("pr_title"),
            "base_ref": snapshot.get("base_ref"),
            "head_ref": snapshot.get("head_ref"),
            "head_sha": snapshot.get("head_sha"),
            "draft": snapshot.get("draft"),
            "mergeable": snapshot.get("mergeable"),
            "mergeable_state": snapshot.get("mergeable_state"),
            "checks_summary": snapshot.get("checks_summary"),
            "html_url": snapshot.get("html_url"),
        },
    }
    if contract.source_mission_id:
        safe_payload["source_mission_id"] = str(contract.source_mission_id)

    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_requested",
        actor_type="system",
        actor_id="github_pr_merge_workflow",
        payload=safe_payload,
    )

    await session.refresh(approval)
    return approval


async def execute_github_pr_merge_after_approval(
    session: AsyncSession,
    approval: Approval,
) -> None:
    settings = get_settings()
    token = (settings.JARVIS_GITHUB_TOKEN or "").strip()
    mid = approval.mission_id
    raw = (approval.command_text or "").strip()

    receipts = ReceiptService(session)
    missions = MissionRepository(session)

    if not raw:
        await _failure_path(
            session,
            receipts,
            missions,
            mid,
            None,
            GitHubPullRequestMergeResult(
                success=False,
                repo="",
                pull_number=None,
                merge_method="squash",
                error_code="missing_contract",
                error_message="Approval had no structured command_text payload.",
            ),
        )
        await session.commit()
        return

    try:
        contract = GitHubMergePullRequestContract.model_validate_json(raw)
    except Exception as e:
        await _failure_path(
            session,
            receipts,
            missions,
            mid,
            None,
            GitHubPullRequestMergeResult(
                success=False,
                repo="",
                pull_number=None,
                merge_method="squash",
                error_code="invalid_contract",
                error_message=str(e)[:500],
            ),
        )
        await session.commit()
        return

    if not token:
        await _failure_path(
            session,
            receipts,
            missions,
            mid,
            contract,
            GitHubPullRequestMergeResult(
                success=False,
                repo=contract.repo,
                pull_number=contract.pull_number,
                merge_method=contract.merge_method,
                error_code="missing_token",
                error_message="JARVIS_GITHUB_TOKEN is not set on the control plane.",
            ),
        )
        await session.commit()
        return

    ok, err_code, err_msg, snap = await preflight_merge(token=token, contract=contract)
    if not ok:
        await _failure_path(
            session,
            receipts,
            missions,
            mid,
            contract,
            GitHubPullRequestMergeResult(
                success=False,
                repo=contract.repo,
                pull_number=contract.pull_number,
                merge_method=contract.merge_method,
                title=str(snap.get("pr_title") or ""),
                html_url=str(snap.get("html_url") or "") or None,
                error_code=err_code or "preflight_failed",
                error_message=err_msg or "Preflight failed before merge.",
            ),
        )
        await session.commit()
        return

    head_sha = str(snap.get("head_sha") or "")
    result = await merge_pull_request(
        token=token,
        repo=contract.repo,
        pull_number=contract.pull_number,
        merge_method=contract.merge_method,
        commit_title=contract.commit_title,
        commit_message=contract.commit_message,
        head_sha=head_sha or None,
    )
    if result.success:
        t = str(snap.get("pr_title") or "")
        u = str(snap.get("html_url") or "") or None
        result = result.model_copy(update={"title": t or result.title, "html_url": u or result.html_url})
        await _success_path(session, receipts, missions, mid, contract, result)
    else:
        await _failure_path(session, receipts, missions, mid, contract, result)
    await session.commit()


def _receipt_payload(result: GitHubPullRequestMergeResult) -> dict[str, Any]:
    d: dict[str, Any] = result.model_dump()
    d["github"] = {
        "repo": result.repo,
        "pull_number": result.pull_number,
        "merge_method": result.merge_method,
        "merged": result.merged,
        "merge_sha": result.merge_sha,
        "html_url": result.html_url,
        "title": result.title,
    }
    return d


async def _success_path(
    session: AsyncSession,
    receipts: ReceiptService,
    missions: MissionRepository,
    mission_id: UUID,
    contract: GitHubMergePullRequestContract,
    result: GitHubPullRequestMergeResult,
) -> None:
    payload = _receipt_payload(result)
    summary = f"Merged PR #{result.pull_number} in {result.repo}" + (
        f" ({result.merge_sha})" if result.merge_sha else ""
    )
    await receipts.record_receipt(
        mission_id=mission_id,
        receipt_type="github_pull_request_merged",
        source="github_integration",
        payload=payload,
        summary=summary,
    )
    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_executed",
        actor_type="system",
        actor_id="github_integration",
        payload={
            "provider": "github",
            "action": "merge_pull_request",
            "repo": result.repo,
            "pull_number": result.pull_number,
            "merge_method": result.merge_method,
            "merge_sha": result.merge_sha,
            "html_url": result.html_url,
            "title": result.title,
        },
    )
    await missions.update_status(mission_id, "complete")
    log.info(
        "github pr merged mission_id=%s repo=%s pr=%s",
        mission_id,
        result.repo,
        result.pull_number,
    )


async def _failure_path(
    session: AsyncSession,
    receipts: ReceiptService,
    missions: MissionRepository,
    mission_id: UUID,
    contract: GitHubMergePullRequestContract | None,
    result: GitHubPullRequestMergeResult,
) -> None:
    payload = _receipt_payload(result)
    summary = result.error_message or "GitHub PR merge failed"
    await receipts.record_receipt(
        mission_id=mission_id,
        receipt_type="github_pull_request_merge_failed",
        source="github_integration",
        payload=payload,
        summary=f"{summary} ({result.error_code or 'error'})",
    )
    await MissionEventRepository.create(
        session,
        mission_id=mission_id,
        event_type="integration_action_failed",
        actor_type="system",
        actor_id="github_integration",
        payload={
            "provider": "github",
            "action": "merge_pull_request",
            "repo": result.repo or (contract.repo if contract else ""),
            "pull_number": result.pull_number if result.pull_number is not None else (contract.pull_number if contract else None),
            "error_code": result.error_code,
            "error_message": result.error_message,
        },
    )
    await missions.update_status(mission_id, "failed")
    log.warning(
        "github pr merge failed mission_id=%s code=%s",
        mission_id,
        result.error_code,
    )
