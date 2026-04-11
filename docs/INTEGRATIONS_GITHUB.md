# Governed GitHub integration (create issue only)

This repo implements **one** integration workflow: **create a GitHub issue**, gated by **operator approval**, with **truthful receipts** and **mission timeline events**. It is not a generic integrations platform.

## Authority

- **Control plane** stores missions, approvals, receipts, and timeline events.
- **GitHub** is the external system of record for the issue once created.
- Workspace markdown does **not** perform this action; callers use the HTTP API with an API key.

## API

`POST /api/v1/missions/{mission_id}/integrations/github/create-issue`

- **Auth:** `x-api-key` (same as other governed routes).
- **Body:** see `GitHubCreateIssueRequest` in `app/schemas/github_issue.py` (`repo`, `title`, `body`, optional `labels` / `assignees` / `milestone`, plus `requested_by`, `requested_via`).
- **Effect:** creates a **pending approval** with structured JSON in `command_text` (`GitHubCreateIssueContract`). Emits `integration_action_requested`. Mission status becomes `awaiting_approval`.

**After approval** (`POST /api/v1/approvals/{id}/decision` with `approved`), the control plane calls GitHub REST **directly** (no executor/OpenClaw path for this workflow).

## Configuration

| Variable | Required | Purpose |
|----------|----------|---------|
| `JARVIS_GITHUB_TOKEN` | **Yes**, for real issue creation | GitHub PAT (classic `repo` scope for private repos, or fine-grained token with **Issues: write** on the target repository). Set on the **control plane host** (e.g. `services/control-plane/.env`). Never commit. |

If the token is missing, the workflow records `github_issue_failed` and `integration_action_failed` with `error_code=missing_token` and an honest operator-facing message.

## Risk / approvals

- `action_type`: `github_create_issue`
- `risk_class`: `red` (identity-bearing external write)
- Human-readable `reason`: `Create GitHub issue in owner/repo: title`

## Receipts and events

| Artifact | Meaning |
|----------|---------|
| `integration_action_requested` | Structured request recorded (repo/title; no secrets). |
| `approval_requested` / `approval_resolved` | Standard governance events. |
| `github_issue_created` or `github_issue_failed` | Receipt types with **safe** payload (`issue_number`, `html_url`, `repo`, `title`, `labels`; errors without raw HTTP bodies). |
| `integration_action_executed` or `integration_action_failed` | Short mission events for the integration outcome. |
| `mission_status_changed` | Mission moves to `complete` or `failed` as appropriate. |

## Verify locally

1. Control plane up with DB and `CONTROL_PLANE_API_KEY`.
2. Create a mission (`POST /api/v1/commands` or existing flow).
3. `POST .../integrations/github/create-issue` with valid body.
4. Approve via `POST /api/v1/approvals/{id}/decision` (or Command Center).
5. Inspect mission timeline and Activity; confirm issue in GitHub if token is valid.
