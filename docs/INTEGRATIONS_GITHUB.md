# Governed GitHub integration (issue, draft PR, PR merge)

This repo implements **three** narrow integration workflows on the **control plane**, all **approval-gated** with **truthful receipts** and **mission timeline events**. They are not a generic GitHub platform.

| Workflow | API | Approval `action_type` | Receipt types |
|----------|-----|------------------------|---------------|
| Create issue | `POST .../integrations/github/create-issue` | `github_create_issue` | `github_issue_created` / `github_issue_failed` |
| Create draft PR (existing branches) | `POST .../integrations/github/create-pull-request` | `github_create_pull_request` | `github_pull_request_created` / `github_pull_request_failed` |
| Merge PR (preflight + re-check) | `POST .../integrations/github/merge-pull-request` | `github_merge_pull_request` | `github_pull_request_merged` / `github_pull_request_merge_failed` |

**Out of scope:** auto-merge, branch deletion, review submission, PR comments, deploy hooks, or generic GitHub abstraction.

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

### Merge pull request

`POST /api/v1/missions/{mission_id}/integrations/github/merge-pull-request`

- **Body:** `GitHubMergePullRequestRequest` — see `app/schemas/github_pr_merge.py`: `repo`, `pull_number`, optional `merge_method` (`merge` \| `squash` \| `rebase`, default **`squash`**), `commit_title`, `commit_message`, `expected_head_sha`, `source_mission_id`, plus `requested_by`, `requested_via`.
- **Requires** `JARVIS_GITHUB_TOKEN` on the control plane **before** approval is created: the server runs **preflight** (GET PR + check runs). If preflight fails, the API returns **409** with `error_code` / `message` — **no approval**.
- **Preflight (v1, conservative):** PR must exist, be **open**, **not draft**, `mergeable` must be **true** (not unknown), `mergeable_state` must be allowed (e.g. **`clean`** or **`behind`**); **`unstable`** / **dirty** / **blocked** / **unknown** reject; **GitHub Check runs** on the head commit: if any run is **queued/in_progress**, or **failed** conclusion → **merge refused**; if the check-runs API cannot be read → **fail honestly** (`checks_unavailable`). Empty check runs (no CI) is OK if the PR is mergeable.
- **After approval:** preflight runs **again**, then `PUT .../pulls/{n}/merge` with optional `sha` (head) for GitHub’s race guard.

**After approval** on issue/PR create/merge, the control plane calls GitHub REST **directly** (no executor/OpenClaw path).

## Configuration

| Variable | Required | Purpose |
|----------|----------|---------|
| `JARVIS_GITHUB_TOKEN` | **Yes**, for real calls | GitHub PAT on the **control plane host** (e.g. `services/control-plane/.env`). **Never commit.** |

- **Issues:** classic PAT with `repo` scope (private repos) or fine-grained token with **Issues: write** on the target repo.
- **Pull requests (create):** **Pull requests: write** (fine-grained) or classic `repo` scope.
- **Merge:** same token must allow **merging** pull requests (contents write / merge) — fine-grained **Pull requests: write** or classic `repo`. Missing scope surfaces as `github_http_403` / GitHub error message in receipts (no raw token).

If the token is missing, create/merge request endpoints that need preflight return **400**; post-approval execution records `*_failed` receipts with `error_code=missing_token` when applicable.

## Risk / approvals

| Workflow | `action_type` | `risk_class` | Notes |
|----------|---------------|----------------|-------|
| Issue | `github_create_issue` | `red` | — |
| Create PR | `github_create_pull_request` | `red` | — |
| Merge PR | `github_merge_pull_request` | `red` | `reason` includes merge method, base, title, checks summary when available |

## Receipts and events

| Artifact | Meaning |
|----------|---------|
| `integration_action_requested` | Structured request; merge includes **`preflight`** snapshot (title, refs, head SHA, checks summary). |
| `approval_requested` / `approval_resolved` | Standard governance events. |
| Success/failure receipt types | Safe payloads (`github` object; no raw HTTP bodies). |
| `integration_action_executed` / `integration_action_failed` | Short mission events (`action`: `create_issue` \| `create_pull_request` \| `merge_pull_request`). |
| Mission status | `complete` or `failed` when the integration run finishes. |

## Verify locally

1. Control plane + DB + `CONTROL_PLANE_API_KEY`.
2. Create a mission (`POST /api/v1/commands` or UI).
3. Call the relevant `.../integrations/github/...` endpoint with a valid body.
4. Approve via Command Center or `POST /api/v1/approvals/{id}/decision`.
5. Inspect mission timeline, Activity, and GitHub.
