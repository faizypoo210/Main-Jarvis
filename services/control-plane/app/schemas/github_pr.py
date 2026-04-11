"""Governed GitHub draft PR workflow — create pull request from existing branches only."""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.approvals import ApprovalSurface

_REPO_RE = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
# GitHub accepts branch names and cross-repo heads like "other-owner:branch"; defer strict checks to the API.
_REF_MAX = 255


class GitHubCreatePullRequestContract(BaseModel):
    """Structured payload for github_create_pull_request approvals — existing head/base only."""

    provider: Literal["github"] = "github"
    action: Literal["create_pull_request"] = "create_pull_request"
    repo: str = Field(..., description="owner/name")
    base: str = Field(..., min_length=1, max_length=_REF_MAX, description="Base ref (branch name)")
    head: str = Field(..., min_length=1, max_length=_REF_MAX, description="Head ref (branch or user:branch)")
    title: str = Field(..., min_length=1, max_length=256)
    body: str = Field("", max_length=65536)
    draft: bool = Field(True, description="Draft PR (default true for this workflow)")
    maintainer_can_modify: bool | None = Field(
        True, description="GitHub maintainer_can_modify; omit behavior if null"
    )
    source_mission_id: UUID | None = Field(
        None, description="Optional originating mission reference (audit only)"
    )

    @field_validator("repo")
    @classmethod
    def repo_format(cls, v: str) -> str:
        s = v.strip()
        if not _REPO_RE.match(s):
            raise ValueError("repo must look like owner/name")
        return s

    @field_validator("base", "head")
    @classmethod
    def ref_nonempty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("base and head are required")
        return s


class GitHubCreatePullRequestRequest(GitHubCreatePullRequestContract):
    """POST body to request a governed GitHub PR (creates approval)."""

    requested_by: str = Field(..., min_length=1, max_length=256)
    requested_via: ApprovalSurface


class GitHubPullRequestResult(BaseModel):
    """Safe subset for receipts (no secrets)."""

    success: bool
    provider: Literal["github"] = "github"
    action: Literal["create_pull_request"] = "create_pull_request"
    repo: str
    base: str
    head: str
    title: str
    pr_number: int | None = None
    html_url: str | None = None
    draft: bool | None = None
    error_code: str | None = None
    error_message: str | None = None
