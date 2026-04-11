# Status ledger (honest, repo-grounded)

Categorization of **major surfaces** as they exist **today** in this repository. Status reflects **code + docs inspection**, not roadmap promises.

| Area | Status | Truth source | Note | Suggested verification |
|------|--------|--------------|------|-------------------------|
| **Control Plane** — missions, events, approvals, receipts, commands, bundle, health | **Implemented** | `services/control-plane/app/api/routes/`, PostgreSQL | Authoritative API for governed state | `GET /health`, `13-rehearse-golden-path.ps1` |
| **Control Plane** — workers / integrations / cost **HTTP API** | **Partial** | DB models in `app/models/` | Tables exist in migrations; **no** `api/routes` modules for these domains found in current tree | Schema review + future route audit |
| **Control Plane** — SSE updates | **Implemented** | `app/api/routes/updates.py`, realtime hub | Stream + status endpoint | Command Center live badge; curl SSE as in benchmark docs |
| **Command Center** — overview, missions, mission detail, approvals | **Implemented** | `services/command-center/src/pages/` | Core operator flows | `npm run build`; manual UI pass |
| **Command Center** — activity feed | **Placeholder** | UI only | Single static message; no unified stream | N/A |
| **Command Center** — integrations / workers / cost / system | **Placeholder** | `App.tsx` → `PlaceholderPage` | Copy says “wired next” | N/A |
| **Coordinator** | **Implemented** | `coordinator/coordinator.py` | Stateless; DashClaw + Redis + control plane | Env set; run `09-start-coordinator.ps1`; observe logs |
| **Executor** | **Implemented** | `executor/executor.py` | OpenClaw + receipts | Live stack rehearsal doc |
| **Voice** | **Implemented** | `voice/server.py` | STT/TTS + control plane hooks | Start server; hit health/static routes per deployment |
| **Approvals (end-to-end)** | **Implemented** | Control plane + UI + scripts | Shared schema `app/schemas/approvals.py` | Golden path script |
| **Benchmark / operator evals** | **Implemented** | `scripts/15-benchmark-operator-loop.ps1`, `docs/OPERATOR_EVALS.md` | Assumes control plane up; optional live stack | Run scripts; inspect `docs/reports/` output |
| **Model lanes** | **Partial** (documented + code paths) | `docs/MODEL_LANES.md`, executor/voice | Lane selection depends on **gateway model string** and **machine** OpenClaw/Ollama | `MODEL_LANES.md` verification section |
| **Integrations (product)** | **Placeholder** UI; **External** OpenClaw/Composio | OpenClaw workspace + vendor | DB `integrations` table exists; Command Center page not wired | Composio/OpenClaw docs |
| **Worker / cost / system health pages** | **Placeholder** | N/A | No dedicated API-backed pages in Command Center | N/A until routes exist |
| **OpenClaw workspace markdown (SOUL, AGENTS, TOOLS, …)** | **Implemented** (tracked mirrors) | `config/workspace/`, `docs/OPENCLAW_WORKSPACE_FILES.md` | Persona/policy/tool rules for the agent; **not** mission authority (control plane) | Sync script + file-by-file doc |
| **Memory / governance docs** | **Implemented** (docs) | `docs/SECURITY_REVIEW.md`, etc. | Security/trust separate from workspace persona files | — |
| **Deployment / smoke automation** | **Partial** | `DEPLOYMENT_STATUS.md`, `scripts/08-*.ps1` | Phase 8 and some checks may still need manual green | `08-final-report.ps1`, `docs/E2E_SMOKE_TEST.md` |

## Legend

- **Implemented**: Usable end-to-end for the stated scope in a correctly configured dev environment.
- **Partial**: Substantial code exists but gaps (missing routes, incomplete UI, or environment-only behavior).
- **Placeholder**: Intentional stub; not a hidden production feature.
- **External / Machine-local**: Depends on installs, secrets, or repos outside this clone.
- **Planned**: Reserved for items explicitly tracked in roadmap docs—not used here without a doc reference.
