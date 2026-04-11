# Governed Gmail integration (create draft, reply draft in thread, send existing draft)

Jarvis can create a **Gmail draft**, create a **reply draft inside an existing thread** (referenced by Gmail message id), or **send an existing draft** as mission work: structured contracts, **approval** (risk **red**), then Gmail REST on the **control plane** host. **No** freeform compose-and-send in one step for arbitrary bodies, **no** inbox listing or polling, **no** Composio/OpenClaw path in these workflows.

## APIs

### Create draft

`POST /api/v1/missions/{mission_id}/integrations/gmail/create-draft`

- **Auth:** `x-api-key`
- **Body:** `GmailCreateDraftRequest` — `to`, `subject`, `body`, optional `cc`, `bcc`, `reply_to_message_id`, `thread_id`, `source_mission_id`, plus `requested_by`, `requested_via`
- **Effect:** pending approval (`gmail_create_draft`), `integration_action_requested` with safe preview (`to_preview`, `subject`), mission `awaiting_approval`
- **After approval:** `users.drafts.create`

### Reply draft (existing thread)

`POST /api/v1/missions/{mission_id}/integrations/gmail/create-reply-draft`

- **Auth:** `x-api-key`
- **Body:** `GmailCreateReplyDraftRequest` — structured contract:
  - `provider`: `"gmail"`
  - `action`: `"create_reply_draft"`
  - `reply_to_message_id` (required) — Gmail API **message id** of the message you are replying to (not the RFC `Message-ID` header string)
  - optional: `thread_id` (must match the message’s thread if set), `to_preview`, `subject`, `body`, `cc`, `bcc`, `source_mission_id`
  - plus `requested_by`, `requested_via`
- **Preflight (before approval):** the control plane calls `users.messages.get` with `format=metadata` to verify the message exists and to build operator-readable preview (subject, snippet, thread id, reply recipient). If Gmail is not configured, the API returns **503** with the same guidance as other Gmail workflows. If the message cannot be read, **400**.
- **Effect:** pending approval (`gmail_create_reply_draft`), `integration_action_requested` with safe fields (`reply_to_message_id`, `thread_id`, `subject_preview`, `to_preview`, `snippet_preview`); mission awaits approval — **no draft is created until approval**.
- **After approval:** resolve reply recipient from headers, build `In-Reply-To` / `References` from the source **Message-ID** header, then `users.drafts.create` with the thread id so the draft stays in-thread. **Does not send.**

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
| Reply draft | `messages.get` (metadata) + `drafts.create` | Same as create draft — **`gmail.compose`** (needs read **one** message by id, not inbox sync) |
| Send draft | `drafts.send` | **`gmail.send`** (per Gmail API reference for `users.drafts.send`) |

If the token only has `gmail.compose`, **create-draft** and **reply-draft** may work while **send-draft** fails with HTTP 403 from Google — configure a token that includes **`gmail.send`** (or a broader scope that includes send).

**Reply-draft:** uses the **same** `JARVIS_GMAIL_*` machine-local auth as create-draft. You need permission to **read** the referenced message (`messages.get`) and **create** drafts — typical OAuth scopes include `gmail.compose` and `gmail.readonly` (or a broader Gmail scope) so metadata lookup succeeds.

## Receipts

| Receipt type | When |
|--------------|------|
| `gmail_draft_created` / `gmail_draft_failed` | After approved create-draft |
| `gmail_reply_draft_created` / `gmail_reply_draft_failed` | After approved reply-draft |
| `gmail_draft_sent` / `gmail_draft_send_failed` | After approved send-draft |

Payloads include a safe `gmail` object (`operation`, `draft_id`, `to_preview`, `subject`, `message_id`, `thread_id`, `reply_to_message_id` for reply-draft, `snippet` when safe, `gmail_url`) — **no** raw provider dumps or secrets.

Mission events: **`integration_action_executed`** / **`integration_action_failed`** with `provider`, `action` (`create_draft`, `create_reply_draft`, or `send_draft`), and the same safe fields.

### Missing auth / config

If Gmail env is not set or token refresh fails, send-draft (or create-draft) records **`gmail_draft_send_failed`** / **`gmail_draft_failed`** with `error_code` such as `missing_gmail_auth`, plus a short operator-readable `error_message`. The mission ends **failed**; the operator must set `JARVIS_GMAIL_*` and retry with a new mission/approval as appropriate.

For **reply-draft**, missing auth at **request** time returns **503** (no approval created yet). Missing auth **after** approval (token removed mid-flight) records **`gmail_reply_draft_failed`** with `missing_gmail_auth` like other Gmail workflows.

## Honest limits

- **Send path is draft-only** — `drafts.send` with an existing draft id; no ad-hoc body send API in this workflow.
- **No inbox** listing, polling, broad triage, thread summarization, or autonomous follow-up.
- **Reply-draft** only targets **one** message id you already know; there is no “browse inbox” API in this workflow.
- **Composio-connected Gmail** in OpenClaw is a **separate** path; this feature is **control-plane REST** only.

## Verify

1. Control plane + DB + API key.
2. Set token env vars; for send-draft ensure scope includes **`gmail.send`**.
3. Create mission, POST `create-draft`, `create-reply-draft`, or `send-draft`, approve in Command Center or `POST /api/v1/approvals/{id}/decision`.
4. Confirm Gmail UI and timeline/Activity in Command Center.
