# Environment variable matrix

**Rules:** Values are **never** committed. Copy from each service’s `.env.example` into `.env` or set **Windows User** env vars. This matrix describes **purpose** and **required vs optional** only.

Legend: **R** = required for that surface to work as designed; **O** = optional (feature off or degraded without it).

---

## Control plane (`services/control-plane/`)

| Variable | Purpose | R/O | Feature / area | If missing / wrong |
|----------|---------|-----|------------------|----------------------|
| `DATABASE_URL` | Async SQLAlchemy URL (PostgreSQL) | R | All persistence | Control plane fails to start or migrate |
| `REDIS_URL` | Redis for realtime / hub | R | SSE, stream-related paths | Errors when Redis needed |
| `SECRET_KEY` | Signing / internal crypto | R | FastAPI app | Misconfig / startup failure |
| `CONTROL_PLANE_API_KEY` | `x-api-key` for mutating routes | R | Commands, approvals decisions, worker POSTs, heartbeat run | 401 on protected routes |
| `ALLOWED_ORIGINS` | CORS origins | O | Browser clients (Command Center, LAN) | Browser blocks API calls |
| `JARVIS_GITHUB_TOKEN` | GitHub REST | O | Governed GitHub workflows | Workflows fail at execute time |
| `JARVIS_GMAIL_*` | Gmail OAuth / tokens | O | Governed Gmail workflows | Gmail paths fail |
| `JARVIS_SMS_APPROVALS_ENABLED` | Toggle SMS | O | Outbound approval SMS | No SMS; approvals still work |
| `JARVIS_TWILIO_*` | Twilio account + webhook | O | SMS approve/deny/read | SMS disabled or errors |
| `JARVIS_TWILIO_WEBHOOK_BASE_URL` | Public base for inbound URL | O | Inbound signature validation | Inbound SMS may fail |
| `APPROVAL_REMINDERS_ENABLED` | Reminder engine | O | Reminder/escalation rows + optional SMS | No reminder cycle |
| `APPROVAL_*` timing | Intervals, caps | O | Reminder behavior | Defaults or disabled |
| `HEARTBEAT_*` | Stale mission, worker, cost thresholds | O | `POST /heartbeat/run` findings | Fewer / no supervision findings |
| `JARVIS_HEALTH_*` | URLs for system health probes | O | Integrations/system health page | Probes show unknown / warn |

See **`services/control-plane/.env.example`** for the full commented list.

---

## Command Center (`services/command-center/`)

| Variable | Purpose | R/O | Feature | If missing |
|----------|---------|-----|---------|------------|
| `VITE_CONTROL_PLANE_URL` | API base | R | All API calls | UI cannot reach backend |
| `VITE_CONTROL_PLANE_API_KEY` | Browser `x-api-key` | R* | Mutating routes from UI | Read-only or failures on write |
| `VITE_VOICE_SERVER_URL` | Voice HTTP/WS base | O | Voice-related UI | Voice features unavailable |

\*Required for normal operator actions (approvals, commands, etc.).

---

## Voice (`voice/`)

Loaded from process env (optional `.env` beside `server.py`).

| Variable | Purpose | R/O | Feature | If missing |
|----------|---------|-----|---------|------------|
| `CONTROL_PLANE_URL` | API base | O | Default `http://localhost:8001` | Wrong host |
| `CONTROL_PLANE_API_KEY` | Mutating API calls | R | Inbox triage, approvals, governed actions, integrations POST | Voice cannot complete gated actions |
| `REDIS_URL` | Stream fan-out | O | Default local Redis | Fan-out may fail |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Direct ack path | O | Fast local replies | Falls back or silent |
| `WHISPER_DEVICE` | `cpu` vs `cuda` | O | STT performance | Slower or wrong device |
| `JARVIS_VOICE_REQUESTED_BY` | Audit label | O | Governed action `requested_by` | Default voice label |

---

## Heartbeat worker (`heartbeat/heartbeat.py`)

| Variable | Purpose | R/O | Feature | If missing |
|----------|---------|-----|---------|------------|
| `CONTROL_PLANE_URL` | Target API | O | Default localhost:8001 | Wrong host |
| `CONTROL_PLANE_API_KEY` | `POST /heartbeat/run` | R | Worker exits | Process stops |
| `HEARTBEAT_INTERVAL_SEC` | Poll interval | O | Default ~120s | Faster/slower ticks |

---

## Coordinator (`coordinator/`)

| Variable | Purpose | R/O | Feature | If missing |
|----------|---------|-----|---------|------------|
| `REDIS_URL` | Streams | R | Consumer | Cannot run |
| `CONTROL_PLANE_URL` | API | R | Mission/approval writes | Fails |
| `CONTROL_PLANE_API_KEY` | Auth | R | Authenticated calls | 401 |
| `DASHCLAW_BASE_URL` | Guard API | R* | Policy path | *Coordinator path errors if unset |
| `DASHCLAW_API_KEY` | Bearer token | R* | DashClaw | *Same |

---

## Executor (`executor/`)

| Variable | Purpose | R/O | Feature | If missing |
|----------|---------|-----|---------|------------|
| `CONTROL_PLANE_URL` | Receipt POST | R | Execution loop | Fails |
| `CONTROL_PLANE_API_KEY` | Auth | R | Receipts | 401 |
| `REDIS_URL` | `jarvis.execution` | R | Consumption | Cannot run |
| `OPENCLAW_CMD` | Path to CLI | O | Default npm global | `openclaw` not found |

---

## SMS / Twilio (control plane)

| Variable | Purpose | R/O | Feature | If missing |
|----------|---------|-----|---------|------------|
| `JARVIS_SMS_APPROVALS_ENABLED` | Master toggle | O | Outbound codes | No SMS |
| `JARVIS_TWILIO_ACCOUNT_SID` | API auth | R* | Twilio | *If SMS enabled |
| `JARVIS_TWILIO_AUTH_TOKEN` | API auth | R* | Twilio | * |
| `JARVIS_TWILIO_FROM_NUMBER` | Sender | R* | Outbound | * |
| `JARVIS_APPROVAL_SMS_TO_E164` | Operator handset | R* | Matching inbound | * |
| `JARVIS_TWILIO_WEBHOOK_BASE_URL` | Signature validation | R* | Inbound | * |

Details: [`SMS_APPROVALS.md`](SMS_APPROVALS.md).

---

## GitHub (control plane)

| Variable | Purpose | R/O | Feature | If missing |
|----------|---------|-----|---------|------------|
| `JARVIS_GITHUB_TOKEN` | REST calls | O | Issue/PR/merge after approval | Execute step fails |

---

## Gmail (control plane)

| Variable | Purpose | R/O | Feature | If missing |
|----------|---------|-----|---------|------------|
| `JARVIS_GMAIL_ACCESS_TOKEN` | Short-lived access | O* | API calls | *Need refresh or client id/secret |
| `JARVIS_GMAIL_REFRESH_TOKEN` | OAuth refresh | O* | Long-running | * |
| `JARVIS_GMAIL_CLIENT_ID` / `SECRET` | OAuth | O* | Token refresh | * |

See [`INTEGRATIONS_GMAIL.md`](INTEGRATIONS_GMAIL.md).

---

## Machine-wide (common)

These apply across tools and scripts. **Provider secrets for cloud models are not stored in repo `.env` files**; cloud auth for OpenClaw lives under **`%USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json`** (manual, out of git). See [`MINIMAX_SETUP.md`](MINIMAX_SETUP.md).

| Variable | Purpose | R/O | Feature |
|----------|---------|-----|---------|
| `JARVIS_LAN_IP` | Advertised LAN IP in scripts | O | Phone / LAN URLs in `jarvis.ps1` |
| `JARVIS_OPENCLAW_GATEWAY_MODEL` | Default agent **model id** for OpenClaw gateway | O | **Controls** the gateway default model written by `scripts/03-configure-openclaw.ps1` into `%USERPROFILE%\.openclaw\openclaw.json` (unset → local default). Not a repo hardcode. |
| `JARVIS_OPENCLAW_GATEWAY_TOKEN` | Gateway HTTP auth token | R* | Required when running `03-configure-openclaw.ps1` (token embedded in generated JSON). *Set User env before configure. |
| `COMPOSIO_API_KEY` | Composio (if used) | O | OpenClaw plugins |

See also [`MACHINE_SETUP_STATUS.md`](../MACHINE_SETUP_STATUS.md).
