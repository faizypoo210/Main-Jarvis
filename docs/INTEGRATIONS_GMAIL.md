# Governed Gmail integration (create draft + send existing draft)

Jarvis can create a **Gmail draft** or **send an existing draft** as mission work: structured contracts, **approval** (risk **red**), then Gmail REST on the **control plane** host. **No** freeform compose-and-send in one step for arbitrary bodies, **no** inbox automation, **no** Composio/OpenClaw path in these workflows.

## APIs

### Create draft

`POST /api/v1/missions/{mission_id}/integrations/gmail/create-draft`

- **Auth:** `x-api-key`
- **Body:** `GmailCreateDraftRequest` — `to`, `subject`, `body`, optional `cc`, `bcc`, `reply_to_message_id`, `thread_id`, `source_mission_id`, plus `requested_by`, `requested_via`
- **Effect:** pending approval (`gmail_create_draft`), `integration_action_requested` with safe preview (`to_preview`, `subject`), mission `awaiting_approval`
- **After approval:** `users.drafts.create`

### Send existing draft

`POST /api/v1/missions/{mission_id}/integrations/gmail/send-draft`

- **Auth:** `x-api-key`
- **Body:** `GmailSendDraftRequest` — structured contract:
  - `provider`: `"gmail"`
  - `action`: `"send_draft"`
  - `draft_id` (required)
  - optional: `message_id`, `thread_id`, `subject`, `to_preview`, `source_mission_id`
  - plus `requested_by`, `requested_via`
- **Effect:** pending approval (`gmail_send_draft`), `integration_action_requested` with `action: "send_draft"` and inspectable fields; **nothing is sent until approval**
- **After approval:** `users.drafts.send` with body `{"id": "<draft_id>"}` only

Optional fields (`subject`, `to_preview`, etc.) are for **human-readable approval copy** and **receipts**; execution identifies the draft **only** by `draft_id`.

## Auth (machine-local)

These workflows do **not** use Composio or OpenClaw. Configure one of:

| Mode | Variables |
|------|-----------|
| **Short-lived access token** | `JARVIS_GMAIL_ACCESS_TOKEN` |
| **Refresh token** | `JARVIS_GMAIL_REFRESH_TOKEN` + `JARVIS_GMAIL_CLIENT_ID` + `JARVIS_GMAIL_CLIENT_SECRET` |

Set these in `services/control-plane/.env` (or the process environment). **Never commit** tokens.

### OAuth scopes (honest)

| Operation | Gmail API | Typical scope need |
|-----------|-----------|---------------------|
| Create draft | `drafts.create` | at least **`gmail.compose`** (broader Gmail scopes also work) |
| Send draft | `drafts.send` | **`gmail.send`** (per Gmail API reference for `users.drafts.send`) |

If the token only has `gmail.compose`, **create-draft** may work while **send-draft** fails with HTTP 403 from Google — configure a token that includes **`gmail.send`** (or a broader scope that includes send).

## Receipts

| Receipt type | When |
|--------------|------|
| `gmail_draft_created` / `gmail_draft_failed` | After approved create-draft |
| `gmail_draft_sent` / `gmail_draft_send_failed` | After approved send-draft |

Payloads include a safe `gmail` object (`operation`, `draft_id`, `to_preview`, `subject`, `message_id`, `thread_id`, `snippet` when safe, `gmail_url`) — **no** raw provider dumps or secrets.

Mission events: **`integration_action_executed`** / **`integration_action_failed`** with `provider`, `action` (`create_draft` vs `send_draft`), and the same safe fields.

### Missing auth / config

If Gmail env is not set or token refresh fails, send-draft (or create-draft) records **`gmail_draft_send_failed`** / **`gmail_draft_failed`** with `error_code` such as `missing_gmail_auth`, plus a short operator-readable `error_message`. The mission ends **failed**; the operator must set `JARVIS_GMAIL_*` and retry with a new mission/approval as appropriate.

## Honest limits

- **Send path is draft-only** — `drafts.send` with an existing draft id; no ad-hoc body send API in this workflow.
- **No inbox** polling, thread summarization, or autonomous follow-up.
- **Composio-connected Gmail** in OpenClaw is a **separate** path; this feature is **control-plane REST** only.

## Verify

1. Control plane + DB + API key.
2. Set token env vars; for send-draft ensure scope includes **`gmail.send`**.
3. Create mission, POST `create-draft` or `send-draft`, approve in Command Center or `POST /api/v1/approvals/{id}/decision`.
4. Confirm Gmail UI and timeline/Activity in Command Center.
