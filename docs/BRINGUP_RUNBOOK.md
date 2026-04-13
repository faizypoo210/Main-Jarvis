# Bring-up runbook (practical)

**Purpose:** Start and verify the **implemented** Jarvis stack in a sensible order. For **system shape** (what each piece is), see [`ARCHITECTURE_V3.md`](ARCHITECTURE_V3.md). For **env var names**, see [`ENV_MATRIX.md`](ENV_MATRIX.md). For **phase checklist**, see [`../DEPLOYMENT_STATUS.md`](../DEPLOYMENT_STATUS.md).

---

## 1. Minimum viable vs full local

| Goal | What you need |
|------|----------------|
| **API + DB only** | Docker Postgres + Redis, control plane (`:8001`), migrations applied |
| **Operator UI** | Above + Command Center dev server (`:5173`) + `VITE_*` pointing at control plane |
| **Mission execution (E2E path)** | Above + OpenClaw gateway (`:18789`) + Redis streams + **coordinator** + **executor** |
| **Voice** | Control plane + voice server (`:8000`) + `CONTROL_PLANE_API_KEY` on voice |
| **Supervision + reminders** | Control plane + optional **`heartbeat/heartbeat.py`** worker (not started by `jarvis.ps1`) |
| **SMS approvals / reminders SMS** | Control plane env for Twilio + public webhook URL (see [`SMS_APPROVALS.md`](SMS_APPROVALS.md)) |

---

## 2. Recommended start order (matches `jarvis.ps1`)

The repo root script **`jarvis.ps1`** automates this path (Windows). Manual bring-up should follow the **same dependency order**.

**Honesty:** `jarvis.ps1` **starts** processes and **probes** some surfaces with HTTP (control plane `/health`, Command Center and voice `GET /`, gateway `/health` or `/`). It does **not** supervise processes or guarantee long-term health. It prints a **bring-up summary** (healthy vs listening vs started/unverified). **Coordinator** and **executor** have **no HTTP probe in this script** (background processes — “unverified here”). When they **register** with the control plane, Command Center **Workers** / **System Health** show **role readiness** (`ready_state`, reasons) from worker metadata — a separate signal from bring-up.

**Stricter gate:** `scripts/07-verify-jarvis-stack.ps1` runs `jarvis.ps1`, then classifies rows as **HEALTHY** (HTTP OK where implemented), **LISTENING** (TCP or container only, or **gateway** TCP without HTTP), **OPTIONAL_DOWN**, or **DOWN**. It **exits non-zero** if core gates fail (containers, control plane `/health`, gateway listening, Command Center HTTP). Voice and optional services are reported but do not fail that script. See script output for the exact line items.

| Step | Component | Required? | Health check |
|------|-----------|-------------|----------------|
| 1 | **Docker Desktop** | Yes (typical dev) | `docker ps` shows `jarvis-postgres`, `jarvis-redis` |
| 2 | **PostgreSQL** | Yes | `pg_isready` / control plane connects via `DATABASE_URL` |
| 3 | **Redis** | Yes for coordinator/executor/voice fan-out | `redis-cli PING` → `PONG` |
| 4 | **OpenClaw gateway** | Required for **executor** E2E | Port **18789** listening; HTTP may be `/health` or `/` (see verify script) |
| 5 | **Control plane** | Yes | `GET http://localhost:8001/health` → 200 |
| 6 | **Command Center** | Strongly recommended for ops | `GET http://localhost:5173/` (dev server) in addition to port |
| 7 | **Voice server** | Optional | `http://localhost:8000` (WebSocket + HTTP) |
| 8 | **Coordinator** | Optional until you need Redis command path | Logs show stream consumption |
| 9 | **Executor** | Optional until you need OpenClaw runs | Consumes `jarvis.execution` |
| 10 | **Heartbeat worker** | Optional | **Not** in `jarvis.ps1` — start manually (see below) |
| 11+ | **LobsterBoard, Ollama** | Optional / supplemental | Ports 8080, 11434 per `jarvis.ps1` tail |

**Alembic:** Before first use or after pulling migrations, run `alembic upgrade head` from `services/control-plane/` with `DATABASE_URL` set (see `REPO_TRUTH.md`).

---

## 3. Heartbeat worker (manual)

`jarvis.ps1` does **not** start the heartbeat process. To run **supervision** and **approval reminder** evaluation on a schedule:

```powershell
cd F:\Jarvis
# From repo root; use the same Python env you use for shared modules if required
$env:CONTROL_PLANE_API_KEY = "your-key"  # match control plane
python heartbeat\heartbeat.py
```

Requires **`CONTROL_PLANE_API_KEY`** (and optional `CONTROL_PLANE_URL`, `HEARTBEAT_INTERVAL_SEC`). See `heartbeat/heartbeat.py` and [`REPO_TRUTH.md`](../REPO_TRUTH.md).

---

## 4. Smoke and verification (when to run what)

| When | Script / command | What it proves |
|------|------------------|----------------|
| After infra + control plane | `.\scripts\08-test-infrastructure.ps1` | Core: Postgres, Redis, `/health`, gateway |
| Operator API surface | `.\scripts\08-smoke-operator-control-plane.ps1` | Health, operator routes, approvals (bundle if pending) |
| Catalog + inbox/workers/cost | `.\scripts\19-smoke-governed-action-catalog.ps1`, `19-smoke-operator-surfaces.ps1` | Governed catalog parity + extra operator GETs |
| Full Phase 8 aggregate | `.\scripts\08-final-report.ps1` | Infra + gateway + LAN + operator smoke + workspace audit |
| End-of-day handoff | `.\scripts\19-day-wrap-snapshot.ps1` | Markdown report under `docs/reports/` + optional Phase 8 + CC build |
| Live pipeline | `.\scripts\09-smoke-test-e2e.ps1` | Full command → coordinator → executor → receipt (needs full stack) |

See [`E2E_SMOKE_TEST.md`](E2E_SMOKE_TEST.md) for E2E prerequisites.

---

## 5. Full local verification (sanity sequence)

1. `GET http://localhost:8001/health`
2. `.\scripts\08-final-report.ps1` (core green) **or** `.\scripts\19-day-wrap-snapshot.ps1` (broader day-wrap)
3. If validating execution: `.\scripts\09-smoke-test-e2e.ps1` with `CONTROL_PLANE_API_KEY` set

---

## 6. What stays manual by design

- OpenClaw **`openclaw.json`**, **`auth-profiles.json`**, gateway token — under `%USERPROFILE%\.openclaw\`
- Vendor OAuth (Gmail), GitHub PAT, Twilio — User env or secure store; never in git
- Public URL for Twilio inbound webhook (tunnel/ngrok) when testing SMS from the public internet
- Workspace sync: `scripts\10-sync-openclaw-workspace.ps1` after editing `config/workspace/`

---

## 7. Tomorrow: where to resume

Short checklist: [`TOMORROW_RESUME.md`](TOMORROW_RESUME.md). Architecture snapshot: [`ARCHITECTURE_V3.md`](ARCHITECTURE_V3.md). Env lookup: [`ENV_MATRIX.md`](ENV_MATRIX.md).
