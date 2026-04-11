# Governed GitHub integration (create issue + draft pull request)

This repo implements **two** narrow integration workflows on the **control plane**, both **approval-gated** with **truthful receipts** and **mission timeline events**. They are not a generic GitHub platform.

| Workflow | API | Approval `action_type` | Receipt types |
|----------|-----|------------------------|---------------|
| Create issue | `POST .../integrations/github/create-issue` | `github_create_issue` | `github_issue_created` / `github_issue_failed` |
| Create draft PR (existing branches) | `POST .../integrations/github/create-pull-request` | `github_create_pull_request` | `github_pull_request_created` / `github_pull_request_failed` |

**Out of scope:** branch creation, commits, merges, reviews, comments, or sync daemons.

## Authority

- **Control plane** stores missions, approvals, receipts, and timeline events.
- **GitHub** is the external system of record after a successful call.
- Callers use the HTTP API with `x-api-key`; workspace markdown does not perform these actions.

## APIs

### Create issue

`POST /api/v1/missions/{mission_id}/integrations/github/create-issue`

- **Body:** `GitHubCreateIssueRequest` — see `app/schemas/github_issue.py` (`repo`, `title`, `body`, optional `labels` / `assignees` / `milestone`, plus `requested_by`, `requested_via`).
- **Effect:** pending approval, `integration_action_requested`, mission `awaiting_approval`.

### Create pull request (draft by default)

`POST /api/v1/missions/{mission_id}/integrations/github/create-pull-request`

- **Body:** `GitHubCreatePullRequestRequest` — see `app/schemas/github_pr.py`: `repo`, `base`, `head`, `title`, optional `body`, `draft` (default **true**), `maintainer_can_modify`, `source_mission_id`, plus `requested_by`, `requested_via`.
- **Effect:** pending approval with structured `command_text`; **head and base must already exist** on GitHub — the server only calls `POST /repos/{owner}/{repo}/pulls`.

**After approval** (`POST /api/v1/approvals/{id}/decision` with `approved`), the control plane calls GitHub REST **directly** (no executor/OpenClaw path).

## Configuration

| Variable | Required | Purpose |
|----------|----------|---------|
| `JARVIS_GITHUB_TOKEN` | **Yes**, for real calls | GitHub PAT on the **control plane host** (e.g. `services/control-plane/.env`). **Never commit.** |

- **Issues:** classic PAT with `repo` scope (private repos) or fine-grained token with **Issues: write** on the target repo.
- **Pull requests:** same token must allow **creating pull requests** — typically **Pull requests: write** on a fine-grained token, or classic `repo` scope. Missing scope surfaces as `github_http_403` / GitHub error message in receipts (no raw token).

If the token is missing, workflows record `*_failed` receipts with `error_code=missing_token` and an operator-facing message.

## Risk / approvals

| Workflow | `action_type` | `risk_class` | Example `reason` |
|----------|---------------|----------------|------------------|
| Issue | `github_create_issue` | `red` | `Create GitHub issue in owner/repo: title` |
| PR | `github_create_pull_request` | `red` | `Create GitHub draft PR in owner/repo from head into base: title` |

## Receipts and events

| Artifact | Meaning |
|----------|---------|
| `integration_action_requested` | Structured request (repo; for PR also `base`, `head`, `title`, `draft`). |
| `approval_requested` / `approval_resolved` | Standard governance events. |
| Success/failure receipt types | Safe payloads (`github` object with `issue_number` or `pr_number`, `html_url`, `base`/`head` for PRs; errors without raw HTTP bodies). |
| `integration_action_executed` / `integration_action_failed` | Short mission events (`action`: `create_issue` vs `create_pull_request`). |
| Mission status | `complete` or `failed` when the integration run finishes. |

## Verify locally

1. Control plane + DB + `CONTROL_PLANE_API_KEY`.
2. Create a mission (`POST /api/v1/commands` or UI).
3. `POST .../create-issue` or `POST .../create-pull-request` with a valid body (for PR, use branches that exist on the remote).
4. Approve via Command Center or `POST /api/v1/approvals/{id}/decision`.
5. Inspect mission timeline, Activity, and GitHub.
