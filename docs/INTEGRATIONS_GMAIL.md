# Governed Gmail integration (create draft only)

Jarvis can create a **Gmail draft** as mission work: structured contract, **approval** (`gmail_create_draft`, risk **red**), then Gmail API `users.drafts.create`. **No send**, **no inbox** automation, **no** Composio/OpenClaw path in this workflow — credentials live on the **control plane** host.

## API

`POST /api/v1/missions/{mission_id}/integrations/gmail/create-draft`

- **Auth:** `x-api-key`
- **Body:** `GmailCreateDraftRequest` — `to` (list of emails), `subject`, `body`, optional `cc`, `bcc`, `reply_to_message_id`, `thread_id`, `source_mission_id`, plus `requested_by`, `requested_via`
- **Effect:** pending approval, `integration_action_requested` with safe preview (`to_preview`, `subject`), mission `awaiting_approval`

After **approval**, the control plane obtains an OAuth **access token** and calls Gmail REST.

## Auth (machine-local)

This workflow does **not** use Composio or OpenClaw. Configure one of:

| Mode | Variables |
|------|-----------|
| **Short-lived access token** | `JARVIS_GMAIL_ACCESS_TOKEN` — OAuth access token with Gmail scope (e.g. `https://www.googleapis.com/auth/gmail.compose`). Operator refreshes when expired. |
| **Refresh token** | `JARVIS_GMAIL_REFRESH_TOKEN` + `JARVIS_GMAIL_CLIENT_ID` + `JARVIS_GMAIL_CLIENT_SECRET` — standard Google OAuth refresh to obtain access tokens. |

Set these in `services/control-plane/.env` (or the process environment). **Never commit** tokens.

Required Google OAuth scope for drafts: at least **`gmail.compose`**. Broader Gmail scopes also work; this workflow only calls **drafts.create**.

## Receipts

- **`gmail_draft_created`** / **`gmail_draft_failed`** with safe structured fields (`draft_id`, `to_preview`, `subject`, `gmail_url` link to drafts folder — not a deep link to one draft in all cases).
- Mission events: **`integration_action_executed`** / **`integration_action_failed`**.

## Honest limits

- **No send** — only `users.drafts.create`.
- **reply_to_message_id** sets MIME `In-Reply-To` / `References` best-effort; full threading semantics are not guaranteed without a valid `thread_id` when Gmail requires it.
- **Composio-connected Gmail** in OpenClaw is a **separate** path; this feature is **control-plane REST** only.

## Verify

1. Control plane + DB + API key.
2. Set token env vars as above.
3. Create mission, POST `create-draft`, approve in Command Center or `POST /api/v1/approvals/{id}/decision`.
4. Confirm draft in Gmail UI and timeline/Activity in Command Center.
