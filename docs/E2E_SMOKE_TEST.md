# End-to-end smoke test (canonical Jarvis stack)

This document describes **`scripts/09-smoke-test-e2e.ps1`**, which proves the live pipeline:

**Command Center / API** → **Control Plane** (`POST /api/v1/commands`) → **PostgreSQL** (mission + `created` event) → **Redis** `jarvis.commands` → **Coordinator** (DashClaw `/api/guard`) → **Redis** `jarvis.execution` → **Executor** (OpenClaw CLI) → **Control Plane** `POST /api/v1/receipts` → **mission event** `receipt_recorded` (with non-empty `payload.summary`) → **mission status** updated (`complete` / `failed`).

## Prerequisites

| Requirement | Why |
|-------------|-----|
| **Control Plane** on `http://localhost:8001` | Creates missions, events, receipts |
| **PostgreSQL** (`jarvis-postgres`, DB `jarvis_missions`) | Mission state |
| **Redis** (`jarvis-redis`, `:6379`) | Streams `jarvis.commands`, `jarvis.execution`, … |
| **Coordinator** | Consumes `jarvis.commands`, calls DashClaw, publishes `jarvis.execution` |
| **Executor** | Consumes `jarvis.execution`, runs `openclaw agent`, posts receipts |
| **OpenClaw CLI** + **Gateway** | Executor subprocess |
| **DashClaw** (`DASHCLAW_BASE_URL`, `DASHCLAW_API_KEY` on the **coordinator** process) | Guard policy; must return **allow** for the happy-path command text |
| **Ollama** (optional) | Local model fallback; not required for receipt if OpenClaw returns text |
| **`CONTROL_PLANE_API_KEY`** | Set in **User** env or session; must match control plane `.env` |

Set the API key **before** running the script:

```powershell
$env:CONTROL_PLANE_API_KEY = 'your-key-matching-control-plane-env'
```

## Startup order

1. Docker: `jarvis-postgres`, `jarvis-redis` (e.g. `scripts\01-install-docker-databases.ps1` or `jarvis.ps1`).
2. **Control plane** (port **8001**).
3. **Coordinator** (with `coordinator\.env` or env: `REDIS_URL`, `CONTROL_PLANE_URL`, **`DASHCLAW_BASE_URL`**, **`DASHCLAW_API_KEY`**).
4. **Executor** (with `CONTROL_PLANE_URL`, **`CONTROL_PLANE_API_KEY`**, `OPENCLAW_CMD` if needed).
5. **OpenClaw Gateway** (e.g. port **18789**).

Using **`.\jarvis.ps1`** starts the core processes in the order documented in the repo root README.

## Commands

### Happy path (receipt)

```powershell
cd F:\Jarvis
$env:CONTROL_PLANE_API_KEY = '...'   # same as control plane
.\scripts\09-smoke-test-e2e.ps1
```

Optional:

- `JARVIS_SMOKE_COMMAND_TEXT` — override command text (must be **allowed** by your DashClaw guard).
- `JARVIS_SMOKE_API_KEY` — alternate name for the API key.

### Approval path (pending approval only; no destructive actions)

```powershell
.\scripts\09-smoke-test-e2e.ps1 -ApprovalPath
# or
.\scripts\09-smoke-test-approval.ps1
```

- Uses **`JARVIS_SMOKE_APPROVAL_COMMAND`** or **`-ApprovalCommandText`** so DashClaw returns **`requires_approval`** (or an unknown decision, which the coordinator maps to approval).
- Asserts **`GET /api/v1/approvals/pending`** contains a **pending** row for the new mission.
- Does **not** call `POST /api/v1/approvals/{id}/decision`.

## Expected pass / fail

### Happy path — PASS

- Script prints `SMOKE_E2E_PASS receipt_recorded=1 mission_id=...`.

### Happy path — FAIL (common)

| Symptom | Likely layer |
|--------|----------------|
| `Control plane unreachable` | Control plane not running or wrong port / URL |
| `CONTROL_PLANE_API_KEY` missing | Env not set; mismatch with control plane |
| `Postgres` / `Redis` failed | Docker containers down |
| `openclaw status` failed | Gateway CLI / install |
| `awaiting_approval` / `approval_requested` | **DashClaw** denied or required approval for your command — use a more benign `JARVIS_SMOKE_COMMAND_TEXT` or relax DashClaw rules |
| Timeout, no `receipt_recorded` | **Coordinator** not consuming `jarvis.commands`, **DashClaw** unreachable, **Executor** not running, **OpenClaw** failing, or **API key** missing on executor POSTs |

### Approval path — PASS

- `SMOKE_E2E_PASS approval_path=1 mission_id=...`

### Approval path — FAIL

| Symptom | Likely cause |
|--------|----------------|
| `Receipt already recorded` | DashClaw **allowed** execution — use a stricter `-ApprovalCommandText` or adjust DashClaw |
| Timeout, no pending approval | DashClaw never returned `requires_approval`, coordinator not running, or wrong `mission_id` matching |

## Diagnosis quick reference

1. **Control plane**: `GET http://localhost:8001/health`
2. **Coordinator logs**: JSON lines with `command_received`, `execution_publish`, or `dashclaw_unreachable`
3. **Executor**: stdout `EXECUTOR: processing mission_id=...`
4. **OpenClaw**: `openclaw gateway health` and `openclaw agent` manually
5. **DashClaw**: browser/API to your `DASHCLAW_BASE_URL`; guard must match your policy expectations
6. **Model config**: `JARVIS_OPENCLAW_GATEWAY_MODEL` / `openclaw.json` — wrong model affects OpenClaw output, not usually receipt creation (executor still posts a summary string)

## Safety

- Commands are normal API traffic; missions and receipts are visible in the control plane like any other run.
- Approval mode does **not** approve, delete, or mutate identities.
- To clean up later, use mission APIs or DB maintenance as you would for any test missions.
