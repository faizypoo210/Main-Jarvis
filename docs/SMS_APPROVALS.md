# SMS approval readout and resolution (v1)

Narrow **Twilio-only** path: when a **pending approval** is created, the control plane can send one **outbound SMS** with a **six-character code** and short copy from the approval packet. The operator replies with **explicit commands only**:

- `APPROVE <CODE>`
- `DENY <CODE>`
- `READ <CODE>`

**Not accepted:** bare `yes`, `ok`, `do it`, `send it`, `merge it`, or similar.

Decisions use `POST /api/v1/approvals/{id}/decision` with `decided_via: "sms"` and `decided_by` from `JARVIS_TWILIO_INBOUND_DECIDED_BY` (default `sms_operator`).

## Configuration

- `JARVIS_SMS_APPROVALS_ENABLED` — `true` to queue outbound SMS after each new approval (when Twilio + destination are set).
- `JARVIS_TWILIO_ACCOUNT_SID`, `JARVIS_TWILIO_AUTH_TOKEN` — Twilio REST credentials.
- `JARVIS_TWILIO_FROM_NUMBER` — E.164 sender (your Twilio number).
- `JARVIS_APPROVAL_SMS_TO_E164` — operator handset E.164; **inbound `From` must match** (normalized).
- `JARVIS_TWILIO_WEBHOOK_BASE_URL` — **exact** public URL of the inbound route, e.g. `https://example.com/api/v1/integrations/sms/inbound` (used for Twilio request signature validation).
- `JARVIS_TWILIO_INBOUND_SKIP_SIGNATURE_VALIDATION` — `true` only for local tunneling (dangerous in production).
- `JARVIS_TWILIO_INBOUND_DECIDED_BY` — audit label for `decided_by` on SMS decisions.

If SMS is disabled or Twilio is incomplete, **approval creation is unchanged**; SMS is skipped.

## API

- **Inbound (Twilio webhook):** `POST /api/v1/integrations/sms/inbound` — `application/x-www-form-urlencoded` body, **no** `x-api-key`. Response is **TwiML** XML (`application/xml`).

## Data model

Table `approval_sms_tokens`: one row per approval with unique `sms_code`, `status` (`pending` | `used`), timestamps, and optional delivery notes. No secrets.

## Reminder and escalation SMS (v1)

When **`APPROVAL_REMINDERS_ENABLED=true`**, the control plane evaluates **pending** approvals during **`POST /api/v1/heartbeat/run`** (before other heartbeat findings). It persists each attempt in **`approval_reminders`** with a stable **`dedupe_key`** so the same logical reminder is not re-sent every tick.

- **SMS delivery** uses the **same** operator number and **`approval_sms_tokens.sms_code`** as the initial approval SMS (concise `REMINDER` / `ESCALATION` copy; reply instructions unchanged).
- **`APPROVAL_REMINDER_SMS_ENABLED`** must be true **and** the same Twilio + `JARVIS_SMS_APPROVALS_ENABLED` gates as initial SMS must pass, or the row is recorded as **`skipped`** (approvals stay valid; no spammy retries).
- Mission events: **`approval_reminder_sent`**, **`approval_reminder_failed`**, **`approval_escalated`** (skipped attempts are **not** mirrored to mission events, only to `approval_reminders`).
- Operator surfaces: **`GET /api/v1/approvals/{id}/bundle`** includes **`reminder_summary`**; heartbeat may emit **`approval_escalation_pending`** when an escalation SMS was **sent** but the approval is still pending.

## Verification

1. `alembic upgrade head` (migrations `007_approval_sms_tokens`, `008_approval_reminders`).
2. Set env, expose webhook URL to Twilio, create a pending approval with a configured stack.
3. Reply to the SMS with `APPROVE <code>` and confirm mission events / `approval_resolved` in the timeline.
