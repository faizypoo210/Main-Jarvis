"""Minimal GitHub REST adapter: issues, PRs, PR merge, inspection helpers."""

from __future__ import annotations

from typing import Any

import httpx

from app.schemas.github_issue import GitHubCreateIssueContract, GitHubIssueResult
from app.schemas.github_pr import GitHubCreatePullRequestContract, GitHubPullRequestResult
from app.schemas.github_pr_merge import GitHubPullRequestMergeResult, MergeMethod

GITHUB_API = "https://api.github.com"


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


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

    headers = _github_headers(token)

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

    headers = _github_headers(token)

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


async def get_pull_request_json(
    *, token: str, repo: str, pull_number: int
) -> tuple[dict[str, Any] | None, int, str]:
    """GET /repos/{owner}/{repo}/pulls/{pull_number}. Returns (data, status, err_msg)."""
    parsed = _parse_repo(repo)
    if not parsed:
        return None, 0, "invalid_repo"
    owner, name = parsed
    url = f"{GITHUB_API}/repos/{owner}/{name}/pulls/{pull_number}"
    headers = _github_headers(token)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers=headers)
    except httpx.HTTPError as e:
        return None, 0, _truncate(str(e))
    try:
        data = r.json() if r.content else {}
    except Exception:
        data = {}
    if r.status_code // 100 == 2 and isinstance(data, dict):
        return data, r.status_code, ""
    err_msg = ""
    if isinstance(data, dict):
        err_msg = str(data.get("message") or "")
    if not err_msg:
        err_msg = r.text[:300] if r.text else f"HTTP {r.status_code}"
    return None, r.status_code, _truncate(err_msg)


async def get_commit_check_runs_json(
    *, token: str, repo: str, head_sha: str
) -> tuple[dict[str, Any] | None, int, str]:
    """GET /repos/{owner}/{repo}/commits/{sha}/check-runs (first page)."""
    parsed = _parse_repo(repo)
    if not parsed:
        return None, 0, "invalid_repo"
    owner, name = parsed
    sha = head_sha.strip()
    if not sha:
        return None, 0, "invalid_sha"
    url = f"{GITHUB_API}/repos/{owner}/{name}/commits/{sha}/check-runs"
    headers = _github_headers(token)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(url, headers=headers, params={"per_page": 100})
    except httpx.HTTPError as e:
        return None, 0, _truncate(str(e))
    try:
        data = r.json() if r.content else {}
    except Exception:
        data = {}
    if r.status_code // 100 == 2 and isinstance(data, dict):
        return data, r.status_code, ""
    err_msg = ""
    if isinstance(data, dict):
        err_msg = str(data.get("message") or "")
    if not err_msg:
        err_msg = r.text[:300] if r.text else f"HTTP {r.status_code}"
    return None, r.status_code, _truncate(err_msg)


async def merge_pull_request(
    *,
    token: str,
    repo: str,
    pull_number: int,
    merge_method: MergeMethod,
    commit_title: str | None,
    commit_message: str | None,
    head_sha: str | None,
) -> GitHubPullRequestMergeResult:
    """PUT /repos/{owner}/{repo}/pulls/{pull_number}/merge."""
    parsed = _parse_repo(repo)
    if not parsed:
        return GitHubPullRequestMergeResult(
            success=False,
            repo=repo,
            pull_number=pull_number,
            merge_method=merge_method,
            error_code="invalid_repo",
            error_message="repo must be owner/name",
        )

    owner, name = parsed
    url = f"{GITHUB_API}/repos/{owner}/{name}/pulls/{pull_number}/merge"
    body_json: dict[str, Any] = {"merge_method": merge_method}
    if commit_title:
        body_json["commit_title"] = commit_title
    if commit_message is not None:
        body_json["commit_message"] = commit_message
    if head_sha:
        body_json["sha"] = head_sha.strip()

    headers = _github_headers(token)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.put(url, json=body_json, headers=headers)
    except httpx.HTTPError as e:
        return GitHubPullRequestMergeResult(
            success=False,
            repo=repo,
            pull_number=pull_number,
            merge_method=merge_method,
            error_code="http_error",
            error_message=_truncate(str(e)),
        )

    try:
        data = r.json() if r.content else {}
    except Exception:
        data = {}

    if r.status_code // 100 == 2 and isinstance(data, dict):
        merged = bool(data.get("merged")) if "merged" in data else True
        sha = data.get("sha")
        msg = data.get("message")
        return GitHubPullRequestMergeResult(
            success=True,
            repo=repo,
            pull_number=pull_number,
            merge_method=merge_method,
            merged=merged,
            merge_sha=str(sha) if sha else None,
            message=str(msg) if msg else None,
        )

    err_msg = ""
    if isinstance(data, dict):
        err_msg = str(data.get("message") or "")
    if not err_msg:
        err_msg = r.text[:300] if r.text else f"HTTP {r.status_code}"
    return GitHubPullRequestMergeResult(
        success=False,
        repo=repo,
        pull_number=pull_number,
        merge_method=merge_method,
        error_code=f"github_http_{r.status_code}",
        error_message=_truncate(err_msg),
    )
