"""Governed GitHub issue creation contract (TRUTH_SOURCE for integration workflow).

Not a generic integrations platform — single action: create_issue.
"""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.approvals import ApprovalSurface

_REPO_RE = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")


class GitHubCreateIssueContract(BaseModel):
    """Structured, inspectable payload for github_create_issue approvals."""

    provider: Literal["github"] = "github"
    action: Literal["create_issue"] = "create_issue"
    repo: str = Field(..., description="owner/name")
    title: str = Field(..., min_length=1, max_length=256)
    body: str = Field("", max_length=65536)
    labels: list[str] = Field(default_factory=list, max_length=20)
    assignees: list[str] = Field(default_factory=list, max_length=20)
    milestone: int | None = Field(None, description="GitHub milestone number if used")
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

    @field_validator("labels", "assignees")
    @classmethod
    def strip_list(cls, v: list[str]) -> list[str]:
        return [x.strip() for x in v if x and str(x).strip()]


class GitHubCreateIssueRequest(GitHubCreateIssueContract):
    """POST body to request a governed GitHub issue (creates approval)."""

    requested_by: str = Field(..., min_length=1, max_length=256)
    requested_via: ApprovalSurface


class GitHubIssueResult(BaseModel):
    """Safe subset for receipts (no secrets)."""

    success: bool
    provider: Literal["github"] = "github"
    action: Literal["create_issue"] = "create_issue"
    repo: str
    title: str
    issue_number: int | None = None
    html_url: str | None = None
    labels: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
