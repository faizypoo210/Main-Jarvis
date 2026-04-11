"""Governed GitHub PR merge contract — merge existing PR only (TRUTH_SOURCE)."""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.approvals import ApprovalSurface

_REPO_RE = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
MergeMethod = Literal["merge", "squash", "rebase"]


class GitHubMergePullRequestContract(BaseModel):
    """Structured payload for github_merge_pull_request approvals."""

    provider: Literal["github"] = "github"
    action: Literal["merge_pull_request"] = "merge_pull_request"
    repo: str = Field(..., description="owner/name")
    pull_number: int = Field(..., ge=1, le=1_000_000)
    merge_method: MergeMethod = Field("squash", description="Default squash (conservative)")
    commit_title: str | None = Field(None, max_length=256)
    commit_message: str | None = Field(None, max_length=65536)
    expected_head_sha: str | None = Field(
        None,
        description="If set, merge only when PR head SHA matches (race guard)",
    )
    source_mission_id: UUID | None = Field(None, description="Optional audit reference")

    @field_validator("repo")
    @classmethod
    def repo_format(cls, v: str) -> str:
        s = v.strip()
        if not _REPO_RE.match(s):
            raise ValueError("repo must look like owner/name")
        return s

    @field_validator("expected_head_sha")
    @classmethod
    def head_sha_format(cls, v: str | None) -> str | None:
        if v is None or not str(v).strip():
            return None
        s = str(v).strip()
        if len(s) < 7:
            raise ValueError("expected_head_sha must be a full or partial git SHA")
        return s


class GitHubMergePullRequestRequest(GitHubMergePullRequestContract):
    """POST body — creates approval after successful preflight."""

    requested_by: str = Field(..., min_length=1, max_length=256)
    requested_via: ApprovalSurface


class GitHubPullRequestMergeResult(BaseModel):
    """Safe subset for receipts."""

    success: bool
    provider: Literal["github"] = "github"
    action: Literal["merge_pull_request"] = "merge_pull_request"
    repo: str
    pull_number: int | None = None
    merge_method: MergeMethod = "squash"
    merged: bool = False
    merge_sha: str | None = None
    html_url: str | None = None
    title: str | None = None
    message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
