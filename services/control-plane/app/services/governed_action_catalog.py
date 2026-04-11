"""Canonical governed action catalog v1 — single source for launch metadata."""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.governed_action_catalog import (
    GovernedActionCatalogEntryRead,
    GovernedActionCatalogResponse,
    GovernedActionFieldRead,
)


def _entries() -> list[GovernedActionCatalogEntryRead]:
    return [
        GovernedActionCatalogEntryRead(
            action_kind="github_create_issue",
            provider="github",
            title="Create approval request — GitHub issue",
            description="Opens a red-risk approval; issue is created only after approval.",
            route_path_suffix="integrations/github/create-issue",
            approval_action_type="github_create_issue",
            field_order=["repo", "title", "body", "labels"],
            fields=[
                GovernedActionFieldRead(
                    name="repo",
                    type="text",
                    required=True,
                    label="Repo",
                    placeholder="org/repo",
                    help_hint="owner/name",
                    validation_hint="Must look like owner/name.",
                    voice_prompt="Say the GitHub repository as owner slash name, like acme slash repo.",
                ),
                GovernedActionFieldRead(
                    name="title",
                    type="text",
                    required=True,
                    label="Title",
                    voice_prompt="Say the title.",
                ),
                GovernedActionFieldRead(
                    name="body",
                    type="textarea",
                    required=False,
                    label="Body",
                    voice_prompt="Say the body text, or say skip for empty.",
                ),
                GovernedActionFieldRead(
                    name="labels",
                    type="comma_list",
                    required=False,
                    label="Labels",
                    placeholder="bug, enhancement",
                    help_hint="optional, comma-separated",
                    voice_prompt="Optional labels, comma separated, or say skip.",
                ),
            ],
            summary_template=(
                "GitHub issue in {repo}, title {title}. Body {body_state}."
            ),
            voice_internal_kind="gh_issue",
            voice_intro="Starting a GitHub issue approval request.",
        ),
        GovernedActionCatalogEntryRead(
            action_kind="github_create_pull_request",
            provider="github",
            title="Create approval request — GitHub draft PR",
            description="Existing branches only; PR is created only after approval.",
            route_path_suffix="integrations/github/create-pull-request",
            approval_action_type="github_create_pull_request",
            field_order=["repo", "base", "head", "title", "body", "draft"],
            fields=[
                GovernedActionFieldRead(
                    name="repo",
                    type="text",
                    required=True,
                    label="Repo",
                    placeholder="org/repo",
                    voice_prompt="Say the GitHub repository as owner slash name.",
                ),
                GovernedActionFieldRead(
                    name="base",
                    type="text",
                    required=True,
                    label="Base",
                    voice_prompt="Say the base branch name.",
                ),
                GovernedActionFieldRead(
                    name="head",
                    type="text",
                    required=True,
                    label="Head",
                    voice_prompt="Say the head branch or user colon branch.",
                ),
                GovernedActionFieldRead(
                    name="title",
                    type="text",
                    required=True,
                    label="Title",
                    voice_prompt="Say the title.",
                ),
                GovernedActionFieldRead(
                    name="body",
                    type="textarea",
                    required=False,
                    label="Body",
                    voice_prompt="Say the body text, or say skip for empty.",
                ),
                GovernedActionFieldRead(
                    name="draft",
                    type="checkbox",
                    required=False,
                    label="Draft PR",
                    help_hint="Draft PR (Command Center default: on). Voice creates draft PR approvals.",
                    voice_prompt=None,
                ),
            ],
            summary_template=(
                "GitHub draft pull request in {repo}, base {base}, head {head}, title {title}."
            ),
            voice_internal_kind="gh_pr",
            voice_intro="Starting a GitHub draft pull request approval request.",
        ),
        GovernedActionCatalogEntryRead(
            action_kind="github_merge_pull_request",
            provider="github",
            title="Create approval request — merge GitHub PR",
            description="Preflight runs server-side; merge executes only after approval.",
            route_path_suffix="integrations/github/merge-pull-request",
            approval_action_type="github_merge_pull_request",
            field_order=["repo", "pull_number", "merge_method", "expected_head_sha"],
            fields=[
                GovernedActionFieldRead(
                    name="repo",
                    type="text",
                    required=True,
                    label="Repo",
                    placeholder="org/repo",
                    voice_prompt="Say the GitHub repository as owner slash name.",
                ),
                GovernedActionFieldRead(
                    name="pull_number",
                    type="number",
                    required=True,
                    label="PR number",
                    voice_prompt="Say the pull request number.",
                ),
                GovernedActionFieldRead(
                    name="merge_method",
                    type="select",
                    required=True,
                    label="Merge method",
                    options=[
                        {"value": "squash", "label": "squash"},
                        {"value": "merge", "label": "merge"},
                        {"value": "rebase", "label": "rebase"},
                    ],
                    voice_prompt="Say merge method squash, merge, or rebase. Default is squash if you say skip.",
                ),
                GovernedActionFieldRead(
                    name="expected_head_sha",
                    type="text",
                    required=False,
                    label="Expected head SHA",
                    help_hint="optional race guard",
                    voice_prompt="Optional expected head SHA, or say skip.",
                ),
            ],
            summary_template=(
                "Merge GitHub pull request number {pull_number} in {repo} using {merge_method}."
            ),
            voice_internal_kind="gh_merge",
            voice_intro="Starting a GitHub merge approval request.",
        ),
        GovernedActionCatalogEntryRead(
            action_kind="gmail_create_draft",
            provider="gmail",
            title="Create approval request — Gmail new draft",
            description="Draft is created only after approval; does not send.",
            route_path_suffix="integrations/gmail/create-draft",
            approval_action_type="gmail_create_draft",
            field_order=["to", "subject", "body", "cc", "bcc"],
            fields=[
                GovernedActionFieldRead(
                    name="to",
                    type="email_list",
                    required=True,
                    label="To",
                    help_hint="comma-separated",
                    voice_prompt="Say recipient email addresses, separated by commas.",
                ),
                GovernedActionFieldRead(
                    name="subject",
                    type="text",
                    required=True,
                    label="Subject",
                    voice_prompt="Say the email subject.",
                ),
                GovernedActionFieldRead(
                    name="body",
                    type="textarea",
                    required=False,
                    label="Body",
                    voice_prompt="Say the body, or say skip.",
                ),
                GovernedActionFieldRead(
                    name="cc",
                    type="email_list",
                    required=False,
                    label="Cc",
                    voice_prompt="Optional Cc emails, or say skip.",
                ),
                GovernedActionFieldRead(
                    name="bcc",
                    type="email_list",
                    required=False,
                    label="Bcc",
                    voice_prompt="Optional Bcc emails, or say skip.",
                ),
            ],
            summary_template="Gmail draft to {to}, subject {subject}.",
            voice_internal_kind="gm_draft",
            voice_intro="Starting a Gmail draft approval request.",
        ),
        GovernedActionCatalogEntryRead(
            action_kind="gmail_create_reply_draft",
            provider="gmail",
            title="Create approval request — Gmail reply draft",
            description="Reply draft in thread; does not send until approved and executed.",
            route_path_suffix="integrations/gmail/create-reply-draft",
            approval_action_type="gmail_create_reply_draft",
            field_order=[
                "reply_to_message_id",
                "thread_id",
                "body",
                "subject",
                "cc",
                "bcc",
            ],
            fields=[
                GovernedActionFieldRead(
                    name="reply_to_message_id",
                    type="text",
                    required=True,
                    label="Reply-to message id",
                    help_hint="Gmail API id",
                    voice_prompt="Say the Gmail message id to reply to.",
                ),
                GovernedActionFieldRead(
                    name="thread_id",
                    type="text",
                    required=False,
                    label="Thread id",
                    help_hint="optional",
                    voice_prompt="Optionally say thread id, or say skip.",
                ),
                GovernedActionFieldRead(
                    name="body",
                    type="textarea",
                    required=False,
                    label="Body",
                    voice_prompt="Say the reply body, or say skip.",
                ),
                GovernedActionFieldRead(
                    name="subject",
                    type="text",
                    required=False,
                    label="Subject override",
                    voice_prompt="Optional subject override, or say skip.",
                ),
                GovernedActionFieldRead(
                    name="cc",
                    type="email_list",
                    required=False,
                    label="Cc",
                    voice_prompt="Optional Cc, or say skip.",
                ),
                GovernedActionFieldRead(
                    name="bcc",
                    type="email_list",
                    required=False,
                    label="Bcc",
                    voice_prompt="Optional Bcc, or say skip.",
                ),
            ],
            summary_template="Gmail reply draft on message {reply_to_message_id}.",
            voice_internal_kind="gm_reply",
            voice_intro="Starting a Gmail reply draft approval request.",
        ),
        GovernedActionCatalogEntryRead(
            action_kind="gmail_send_draft",
            provider="gmail",
            title="Create approval request — Gmail send existing draft",
            description="Send runs only after approval.",
            route_path_suffix="integrations/gmail/send-draft",
            approval_action_type="gmail_send_draft",
            field_order=["draft_id"],
            fields=[
                GovernedActionFieldRead(
                    name="draft_id",
                    type="text",
                    required=True,
                    label="Draft id",
                    voice_prompt="Say the Gmail draft id.",
                ),
            ],
            summary_template="Send Gmail draft {draft_id}.",
            voice_internal_kind="gm_send",
            voice_intro="Starting a Gmail send-draft approval request.",
        ),
    ]


def governed_entries_by_approval_action_type() -> dict[str, GovernedActionCatalogEntryRead]:
    """Lookup catalog row by stored approval `action_type` (approval_action_type)."""
    return {e.approval_action_type: e for e in _entries() if e.enabled}


def build_governed_action_catalog_response() -> GovernedActionCatalogResponse:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return GovernedActionCatalogResponse(
        catalog_version=1,
        generated_at=now,
        actions=[a for a in _entries() if a.enabled],
    )
