"""Minimal GitHub REST adapter: create issue, create pull request."""

from __future__ import annotations

from typing import Any

import httpx

from app.schemas.github_issue import GitHubCreateIssueContract, GitHubIssueResult
from app.schemas.github_pr import GitHubCreatePullRequestContract, GitHubPullRequestResult

GITHUB_API = "https://api.github.com"


def _truncate(s: str, n: int = 500) -> str:
    t = s.strip()
    return t if len(t) <= n else t[: n - 1] + "…"


async def create_issue(
    *,
    token: str,
    contract: GitHubCreateIssueContract,
) -> GitHubIssueResult:
    """POST /repos/{owner}/{repo}/issues. Returns GitHubIssueResult (success or failure, no secrets)."""
    owner, _, name = contract.repo.partition("/")
    if not owner or not name:
        return GitHubIssueResult(
            success=False,
            repo=contract.repo,
            title=contract.title,
            error_code="invalid_repo",
            error_message="repo must be owner/name",
        )

    url = f"{GITHUB_API}/repos/{owner}/{name}/issues"
    body_json: dict[str, Any] = {
        "title": contract.title,
        "body": contract.body or "",
    }
    if contract.labels:
        body_json["labels"] = contract.labels
    if contract.assignees:
        body_json["assignees"] = contract.assignees
    if contract.milestone is not None:
        body_json["milestone"] = contract.milestone

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=body_json, headers=headers)
    except httpx.HTTPError as e:
        return GitHubIssueResult(
            success=False,
            repo=contract.repo,
            title=contract.title,
            error_code="http_error",
            error_message=_truncate(str(e)),
        )

    try:
        data = r.json() if r.content else {}
    except Exception:
        data = {}

    if r.status_code // 100 == 2 and isinstance(data, dict):
        num = data.get("number")
        html_url = data.get("html_url")
        labels_out: list[str] = []
        for lb in data.get("labels") or []:
            if isinstance(lb, dict) and lb.get("name"):
                labels_out.append(str(lb["name"]))
        return GitHubIssueResult(
            success=True,
            repo=contract.repo,
            title=contract.title,
            issue_number=int(num) if isinstance(num, int) else None,
            html_url=str(html_url) if html_url else None,
            labels=labels_out or contract.labels,
        )

    err_msg = ""
    if isinstance(data, dict):
        err_msg = str(data.get("message") or data.get("error") or "")
    if not err_msg:
        err_msg = r.text[:300] if r.text else f"HTTP {r.status_code}"
    return GitHubIssueResult(
        success=False,
        repo=contract.repo,
        title=contract.title,
        error_code=f"github_http_{r.status_code}",
        error_message=_truncate(err_msg),
    )


def _parse_repo(repo: str) -> tuple[str, str] | None:
    owner, _, name = repo.partition("/")
    if not owner or not name:
        return None
    return owner, name


async def create_pull_request(
    *,
    token: str,
    contract: GitHubCreatePullRequestContract,
) -> GitHubPullRequestResult:
    """POST /repos/{owner}/{repo}/pulls — draft PR from existing head branch."""
    parsed = _parse_repo(contract.repo)
    if not parsed:
        return GitHubPullRequestResult(
            success=False,
            repo=contract.repo,
            base=contract.base,
            head=contract.head,
            title=contract.title,
            error_code="invalid_repo",
            error_message="repo must be owner/name",
        )

    owner, name = parsed
    url = f"{GITHUB_API}/repos/{owner}/{name}/pulls"
    body_json: dict[str, Any] = {
        "title": contract.title,
        "head": contract.head,
        "base": contract.base,
        "body": contract.body or "",
        "draft": contract.draft,
    }
    if contract.maintainer_can_modify is not None:
        body_json["maintainer_can_modify"] = contract.maintainer_can_modify

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(url, json=body_json, headers=headers)
    except httpx.HTTPError as e:
        return GitHubPullRequestResult(
            success=False,
            repo=contract.repo,
            base=contract.base,
            head=contract.head,
            title=contract.title,
            error_code="http_error",
            error_message=_truncate(str(e)),
        )

    try:
        data = r.json() if r.content else {}
    except Exception:
        data = {}

    if r.status_code // 100 == 2 and isinstance(data, dict):
        num = data.get("number")
        html_url = data.get("html_url")
        draft = data.get("draft")
        return GitHubPullRequestResult(
            success=True,
            repo=contract.repo,
            base=contract.base,
            head=contract.head,
            title=contract.title,
            pr_number=int(num) if isinstance(num, int) else None,
            html_url=str(html_url) if html_url else None,
            draft=bool(draft) if isinstance(draft, bool) else contract.draft,
        )

    err_msg = ""
    if isinstance(data, dict):
        err_msg = str(data.get("message") or data.get("error") or "")
    if not err_msg:
        err_msg = r.text[:300] if r.text else f"HTTP {r.status_code}"
    return GitHubPullRequestResult(
        success=False,
        repo=contract.repo,
        base=contract.base,
        head=contract.head,
        title=contract.title,
        error_code=f"github_http_{r.status_code}",
        error_message=_truncate(err_msg),
    )
