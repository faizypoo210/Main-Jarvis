# System map (as reflected in this repo)

Practical map of **what exists in git** and **what sits outside** it. For ownership and verification, see **`REPO_TRUTH.md`**.

**Mechanisms-first read:** for the table of crucial mechanisms (mission authority, Redis, coordinator, executor, OpenClaw split, voice, verification), see **`REPO_TRUTH.md` → “Major mechanisms (crucial for full context)”**. This file expands layout and flows.

## Major components

| Component | Role | In repo? | Typical port / transport |
|-----------|------|----------|----------------------------|
| **Control Plane** | Authoritative API + DB: missions, events, approvals, receipts, updates/SSE | Yes — `services/control-plane/` | HTTP **8001**, PostgreSQL **5432** |
| **Command Center** | Primary operator UI: overview, missions, mission detail, approvals | Yes — `services/command-center/` | HTTP **5173** (dev) |
| **Coordinator** | Reads Redis streams, calls DashClaw guard/outcomes, writes control plane + execution/updates streams | Yes — `coordinator/` | Env to Redis + DashClaw + control plane |
| **Executor** | Consumes `jarvis.execution`, runs OpenClaw CLI, posts receipts to control plane | Yes — `executor/` | Redis consumer |
| **Voice Server** | STT/TTS, WebSocket, forwards intent toward control plane / Redis | Yes — `voice/` | HTTP **8000** |
| **Redis** | Streams and coordination | Docker / host — **not** application code in repo | **6379** |
| **PostgreSQL** | Persistence for control plane | Docker / host | **5432** |
| **OpenClaw Gateway** | Agent/tool runtime for executor | **External** install + `%USERPROFILE%\.openclaw\` | **18789** (per README) |
| **Ollama** | Local inference (voice / optional gateway model) | **External** binary | **11434** |
| **LobsterBoard** | Supplemental dashboard | **External** clone (`C:\projects\LobsterBoard` in deployment docs) | **8080** |
| **DashClaw** | Governance API used by coordinator | **External** service; URL + key via env | Implementation-specific |

## Machine / layer boundaries

```
[Operator browser / phone]
        │
        ├─► Command Center (5173) ──HTTP──► Control Plane (8001) ──► PostgreSQL
        │
        ├─► Voice (8000) ──HTTP/WS──► Control Plane + Redis streams
        │
        └─► (LAN) same as above if firewall + JARVIS_LAN_IP configured

Redis (6379)
   ◄── Coordinator ◄── reads jarvis.commands, jarvis.receipts (etc.)
   │       │
   │       ├──► Control Plane (HTTP) — mission/approval/receipt writes
   │       ├──► DashClaw — guard / outcomes (when used)
   │       └──► writes jarvis.execution, jarvis.updates

Executor ◄── jarvis.execution
   └──► OpenClaw CLI ──► Gateway ──► models (Ollama lane or cloud via auth profiles)
   └──► POST receipts ──► Control Plane
```

## Major flows

1. **Command → mission**: `POST /api/v1/commands` (control plane); may publish to Redis for runtime consumers depending on payload (see `docs/GOLDEN_PATH.md` for rehearsal isolation).
2. **Approval**: Rows via `POST /api/v1/approvals` and decisions via `POST /api/v1/approvals/{id}/decision`; coordinator may create approval requests when DashClaw requires it; UI uses same APIs.
3. **Receipts**: Executor (or rehearsal scripts) `POST /api/v1/receipts`; timeline events align with mission detail and Command Center presentation helpers.
4. **Live UI**: Command Center uses SSE (`/api/v1/updates/stream`) with polling fallback (see `services/command-center/README.md`).

## Where approvals happen

- **Persistence and API**: Control Plane (`approvals` routes, `app/schemas/approvals.py`).
- **Policy suggestion**: DashClaw when the coordinator path is active (`coordinator/coordinator.py` and env).
- **Human decision**: Command Center (and potentially voice UI buttons—see Command Center README for voice limitations).

## Where receipts are written

- **Executor** posts to **`POST /api/v1/receipts`** after OpenClaw runs (`executor/executor.py`).
- **Golden-path script** uses the same endpoint for verification (`scripts/13-rehearse-golden-path.ps1`).

## OpenClaw vs this repo

- **In repo**: execution worker code, workspace **mirrors** (`config/workspace/` — see **`governance-manifest.json`** and **`docs/OPENCLAW_WORKSPACE_FILES.md`**), scripts, UI.
- **Machine-local**: `openclaw.json`, auth profiles, plugins, **live** `%USERPROFILE%\.openclaw\workspace\main\` (must be updated via sync or manual copy)—**MACHINE_CONFIG_REQUIRED**.

## Command Center vs control plane

- Command Center is a **client** of the control plane. It does not store authoritative mission rows.
- **Placeholder routes** (integrations, workers, cost, system health) are not separate backends in this repo—they are UI stubs until backed by APIs.
