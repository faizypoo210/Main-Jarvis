# Status ledger (honest, repo-grounded)

Categorization of **major surfaces** as they exist **today** in this repository. Status reflects **code + docs inspection**, not roadmap promises.

| Area | Status | Truth source | Note | Suggested verification |
|------|--------|--------------|------|-------------------------|
| **Control Plane** — missions, events, approvals, receipts, commands, bundle, health | **Implemented** | `services/control-plane/app/api/routes/`, PostgreSQL | Authoritative API for governed state | `GET /health`, `13-rehearse-golden-path.ps1` |
| **Control Plane** — operator read APIs (system health, usage, activity, integrations, **memory**) | **Implemented** | `app/api/routes/system.py`, `app/api/routes/operator.py`, `app/api/routes/operator_memory.py` | Operator memory is **durable context** in `memory_items` — separate from mission rows and chat | `GET /api/v1/operator/memory`, `GET /api/v1/operator/memory/counts`, `npm run build`, `/memory` in Command Center |
| **Control Plane** — workers / cost **domain tables** (non-mission) | **Partial** | `app/models/` | Tables exist; first-class REST CRUD for workers/cost may still be missing | Schema / route audit |
| **Control Plane** — SSE updates | **Implemented** | `app/api/routes/updates.py`, realtime hub | Stream + status endpoint | Command Center live badge; curl SSE as in benchmark docs |
| **Command Center** — overview, missions, mission detail, approvals | **Implemented** | `services/command-center/src/pages/` | Core operator flows | `npm run build`; manual UI pass |
| **Command Center** — activity feed | **Implemented** | `pages/Activity.tsx`, `GET /api/v1/operator/activity` | Mission-event timeline; filters | `npm run build`; hit `/activity` |
| **Command Center** — workers, cost & usage, system health | **Implemented** | `pages/*.tsx`, operator + system APIs | Operator surfaces backed by control plane | `npm run build` |
| **Command Center** — integrations | **Implemented** (honest) | `pages/Integrations.tsx`, `GET /api/v1/operator/integrations` | DB + safe machine/repo signals; **no** OAuth or vendor secrets in API | `npm run build`; curl integrations endpoint |
| **Coordinator** | **Implemented** | `coordinator/coordinator.py` | Stateless; DashClaw + Redis + control plane | Env set; run `09-start-coordinator.ps1`; observe logs |
| **Executor** | **Implemented** | `executor/executor.py` | OpenClaw + receipts | Live stack rehearsal doc |
| **Voice** | **Implemented** | `voice/server.py` | STT/TTS + control plane hooks | Start server; hit health/static routes per deployment |
| **Approvals (end-to-end)** | **Implemented** | Control plane + UI + scripts | Shared schema `app/schemas/approvals.py` | Golden path script |
| **Benchmark / operator evals** | **Implemented** | `scripts/15-benchmark-operator-loop.ps1`, `docs/OPERATOR_EVALS.md` | Assumes control plane up; optional live stack | Run scripts; inspect `docs/reports/` output |
| **Model lanes** | **Partial** (documented + code paths) | `docs/MODEL_LANES.md`, `shared/routing.py`, executor/voice | OpenClaw **gateway model** sets executor `execution_meta.lane`; **mission routing** records requested vs actual lane + fallback in `routing_decided` events | `MODEL_LANES.md` verification section; observe `routing_decided` after a command |
| **Integrations (vendor OAuth / Composio)** | **External / partial** | OpenClaw + Composio + machine | UI/API show **readiness only**; OAuth and keys stay outside repo | Vendor consoles + `DEPLOYMENT_STATUS.md` |
| **OpenClaw workspace markdown (SOUL, AGENTS, TOOLS, …)** | **Implemented** (tracked mirrors) | `config/workspace/`, `docs/OPENCLAW_WORKSPACE_FILES.md` | Persona/policy/tool rules for the agent; **not** mission authority (control plane) | Sync script + file-by-file doc |
| **Operator memory (durable v1)** | **Implemented** | `app/models/memory_item.py`, Alembic `003_memory_items`, `memory_promotion.py` | Manual + explicit mission promotion + structured `memory_candidate` on receipts only; **no** vector DB, **no** auto-ingest of missions/commands/logs | `alembic upgrade head`; POST with API key; receipt payload shape in `memory_promotion.py` |
| **Security / governance docs** | **Implemented** (docs) | `docs/SECURITY_REVIEW.md`, etc. | Security/trust separate from workspace persona files | — |
| **Deployment / smoke automation** | **Partial** | `DEPLOYMENT_STATUS.md`, `scripts/08-*.ps1` | Phase 8 and some checks may still need manual green | `08-final-report.ps1`, `docs/E2E_SMOKE_TEST.md` |

## Legend

- **Implemented**: Usable end-to-end for the stated scope in a correctly configured dev environment.
- **Partial**: Substantial code exists but gaps (missing routes, incomplete UI, or environment-only behavior).
- **Placeholder**: Intentional stub; not a hidden production feature.
- **External / Machine-local**: Depends on installs, secrets, or repos outside this clone.
- **Planned**: Reserved for items explicitly tracked in roadmap docs—not used here without a doc reference.
