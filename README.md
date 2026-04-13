# JARVIS — AI Command Center

Personal autonomous AI assistant: **Command Center** (operator UI), **Control Plane** (authoritative API), **Voice Server**, **Coordinator** (Redis), **Executor** (OpenClaw CLI), plus OpenClaw Gateway, LobsterBoard, Ollama, Composio, and DashClaw.  
Deployed on Windows 11 (single-machine / LAN dev; see `docs/SECURITY_REVIEW.md`).

## Repo truth (what this codebase actually owns)

Jarvis is **multi-part**, not a single deployable monolith. Before changing behavior or docs, read:

| Doc | Use |
|-----|-----|
| [`docs/ARCHITECTURE_V3.md`](docs/ARCHITECTURE_V3.md) | **Canonical architecture snapshot:** services, boundaries, state, flows, diagrams |
| [`docs/BRINGUP_RUNBOOK.md`](docs/BRINGUP_RUNBOOK.md) | **Start order, health checks, smoke scripts, minimum vs full stack** |
| [`docs/ENV_MATRIX.md`](docs/ENV_MATRIX.md) | **Environment variables by service** (no secret values) |
| [`docs/TOMORROW_RESUME.md`](docs/TOMORROW_RESUME.md) | **Quick resume** after a break |
| [`REPO_TRUTH.md`](REPO_TRUTH.md) | Ownership, out-of-repo dependencies, authority boundaries, reality labels, verification |
| [`SYSTEM_MAP.md`](SYSTEM_MAP.md) | Short component map; complements Architecture V3 |
| [`STATUS.md`](STATUS.md) | Implemented vs partial vs placeholder surfaces |
| [`MACHINE_SETUP_STATUS.md`](MACHINE_SETUP_STATUS.md) | Env, secrets, OpenClaw paths, prerequisites checklist |

The **`REPO_TRUTH.md`** doc includes a **“Major mechanisms”** section (mission authority, Redis, coordinator, executor, OpenClaw split, voice, verification) so GitHub has explicit context for the parts that matter most—even though live OpenClaw config on disk is not in git. **`docs/OPENCLAW_WORKSPACE_FILES.md`** maps **`SOUL.md`**, **`AGENTS.md`**, **`TOOLS.md`**, and related workspace files to their **behavioral** role (persona vs mission state in the control plane).

## Canonical architecture

Full detail: **[`docs/ARCHITECTURE_V3.md`](docs/ARCHITECTURE_V3.md)** (service map, truth stores, flows, Mermaid diagrams).

| Role | Port | Purpose |
|------|------|---------|
| **Control Plane** (FastAPI) | **8001** | Authoritative source of truth (missions, events, approvals, receipts) |
| **Command Center** (React/Vite) | **5173** | Primary operator UI |
| **Voice Server** (FastAPI/WebSocket) | **8000** | STT/TTS and voice path |
| **Coordinator** | — | Stateless Redis router (streams ↔ control plane) |
| **Executor** | — | Consumes `jarvis.execution`, runs OpenClaw CLI, posts receipts |
| **Redis** | 6379 | Streams / coordination |
| **PostgreSQL** | 5432 | Persistence for control plane |
| **OpenClaw Gateway** | 18789 | Agent runtime (cloud execution via OpenClaw; local fast path via Ollama) |
| **LobsterBoard** | 8080 | Supplemental operator dashboard |
| **Ollama** | 11434 | Local fast model (`qwen3:4b` by default) |

Command Center includes a **shell-level quick command** (keyboard shortcut + header control) so operators can submit short commands from any route; full conversation remains on Overview. Missions are created via the same control-plane **`POST /api/v1/commands`** path as the main composer.

The old **openclaw-mission-control** UI (3000/3001) is **deprecated** and **not** started by `jarvis.ps1`. Code and compose live under **`deprecated/mission-control/`** (manual / quarantined only). **`JARVIS_INCLUDE_MISSION_CONTROL=1`** only prints a **deprecation reminder** in the console — it does **not** auto-start legacy Mission Control. Current operator path: **Command Center + Control Plane**.

## Model stack

| Tier | Default | Notes |
|------|---------|--------|
| Local fast | Ollama `qwen3:4b` | Override with `OLLAMA_MODEL` |
| Cloud execution | Provider via OpenClaw gateway | **Do not hardcode** provider/model slugs in repo; set **`JARVIS_OPENCLAW_GATEWAY_MODEL`** and configure auth outside git—see **[`docs/MINIMAX_SETUP.md`](docs/MINIMAX_SETUP.md)** (MiniMax and other clouds use the same gateway lane) |

### MiniMax / cloud model setup

Cloud models (including MiniMax) are selected with **`JARVIS_OPENCLAW_GATEWAY_MODEL`** and provider credentials in **`%USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json`**, not in tracked `.env` files. Step-by-step: **[`docs/MINIMAX_SETUP.md`](docs/MINIMAX_SETUP.md)**.

## Machine

- Windows 11, AMD Ryzen 5 3600, RTX 4070 Ti, 32GB RAM  
- Same-network access: set User env **`JARVIS_LAN_IP`** to this PC’s IPv4, then use `http://<JARVIS_LAN_IP>:<port>` from other devices (see `jarvis.ps1` / verify scripts).

## Repo structure (`F:\Jarvis`)

```
├── .cursor/rules/          # Cursor AI rules
├── config/                 # Service configs (secrets redacted)
│   └── workspace/          # Tracked mirrors of OpenClaw markdown (see config/workspace/README.md)
├── context/                # Architecture docs and system spec
├── coordinator/            # Redis → control plane
├── executor/               # jarvis.execution → OpenClaw CLI
├── scripts/                # Deployment scripts; includes 10-sync-openclaw-workspace.ps1
├── services/
│   ├── control-plane/      # FastAPI :8001
│   └── command-center/     # Vite :5173
├── voice/                  # FastAPI :8000
├── jarvis.ps1              # Master startup — core stack first, supplemental last
├── START_HERE.md           # Cursor agent entry point
└── DEPLOYMENT_STATUS.md    # Phase checklist
```

## Starting JARVIS

```powershell
cd F:\Jarvis
.\jarvis.ps1
```

**Bring-up vs readiness:** `jarvis.ps1` **initiates** bring-up and prints a **per-surface summary** (what is health-checked via HTTP, what is only listening, what is **started/unverified** — e.g. coordinator and executor have no probe in that script). It does **not** mean “the entire stack is healthy.” For a **stricter readiness gate** (containers + `GET /health` on the control plane + gateway TCP + Command Center HTTP), run **`scripts/07-verify-jarvis-stack.ps1`** after bring-up (it exits non-zero if core gates fail).

**Legacy Mission Control:** not started here. **`JARVIS_INCLUDE_MISSION_CONTROL=1`** only shows an extra deprecation notice; legacy UI is **manual** from `deprecated/mission-control/` if you still need it.

**Primary URLs** (when services are actually up):

- Command Center: http://localhost:5173  
- Control Plane API: http://localhost:8001  
- Voice Server: http://localhost:8000  

## Deployment phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Docker + PostgreSQL + Redis | Complete |
| 2 | Legacy openclaw-mission-control | Quarantined / manual only (`deprecated/mission-control/`); not part of default bring-up |
| 3 | OpenClaw Gateway | Complete |
| 4 | LobsterBoard dashboard | Complete |
| 5 | Ollama + `qwen3:4b` | Complete |
| 6 | Composio integrations | Complete |
| 7 | Firewall + phone access | Complete |
| 8 | E2E testing | In progress |

## Secrets

All secrets live in **Windows User environment variables** and **`%USERPROFILE%\.openclaw\`** — never committed. **Rotation checklist:** [`docs/SECRET_ROTATION.md`](docs/SECRET_ROTATION.md). **Trust model:** [`docs/SECURITY_REVIEW.md`](docs/SECURITY_REVIEW.md).

### Control-plane auth (current model)

- **`CONTROL_PLANE_AUTH_MODE=api_key`** (default): mutating API routes require a valid **`x-api-key`** header matching **`CONTROL_PLANE_API_KEY`** on the server. The process will not start in `api_key` mode with an empty key.
- **`CONTROL_PLANE_AUTH_MODE=local_trusted`**: explicit **rough local dev only** — mutations do **not** enforce the API key (see server logs / `app/core/auth.py`). Not for exposed deployments.
- **Command Center (`npm run dev`):** the Vite dev server reads **`CONTROL_PLANE_API_KEY`** in the **Node** process and **injects** `x-api-key` on proxied `/api` requests (`vite.config.ts`). The key is **not** bundled into the browser client. For serious deployments, use **same-origin** or a **reverse proxy** that attaches the header **server-side**.
- **Voice / workers / scripts** that call the API use **`CONTROL_PLANE_API_KEY`** in the environment of that process (not a browser story).

Examples (set only what your providers require; names follow OpenClaw / vendor docs):

- Composio: `COMPOSIO_API_KEY`  
- OpenClaw gateway token: set **`JARVIS_OPENCLAW_GATEWAY_TOKEN`** before `scripts/03-configure-openclaw.ps1`, or edit `%USERPROFILE%\.openclaw\openclaw.json` manually (never commit)  
- Control plane: `CONTROL_PLANE_API_KEY` in `services/control-plane/.env` (and the same value in Command Center **`.env` for dev proxy** when using `api_key` mode)  
- DashClaw (coordinator): `DASHCLAW_API_KEY`  
- MiniMax / other cloud providers: configure via OpenClaw **`auth-profiles.json`** and env vars **per OpenClaw documentation** (not hardcoded here)

Config files with secrets (not in repo):

- `%USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json`  
- Deprecated UI only: `openclaw-mission-control` `.env` if you still run that stack

## OpenClaw workspace (persona vs code)

| What | Where |
|------|--------|
| **Executable source** | This repo (`services/`, `coordinator/`, `executor/`, …) |
| **Tracked markdown mirrors** | `config/workspace/` — canonical set in `governance-manifest.json` (`SOUL`, `IDENTITY`, `USERS`, `AGENTS`, `MEMORY`, `HEARTBEAT`, `TOOLS`; operator file is **`USERS.md`**, not `USER.md`) |
| **Live files OpenClaw reads** | `%USERPROFILE%\.openclaw\workspace\main\` (`10-sync-openclaw-workspace.ps1`; audit with `11-audit-workspace-governance.ps1`) |
| **Mission state (authoritative)** | Control Plane API + PostgreSQL — not in workspace markdown |

See [docs/WORKSPACE_SYNC.md](docs/WORKSPACE_SYNC.md) and [config/workspace/README.md](config/workspace/README.md).

## Architecture

See [context/ARCHITECTURE.md](context/ARCHITECTURE.md) for service map and data flow.  
See [docs/MODEL_LANES.md](docs/MODEL_LANES.md) for local Ollama vs OpenClaw gateway lanes and verification scripts.  
See [context/JARVIS_SPEC.md](context/JARVIS_SPEC.md) for the broader system specification.

## Automated tests

Control Plane API regression tests (pytest + PostgreSQL) and how to run them locally: **[`docs/TESTING.md`](docs/TESTING.md)**. CI runs the same suite and a **Command Center** `npm run build` guardrail (`.github/workflows/ci.yml`).

## Roadmap

- Phase 8: E2E testing against Control Plane + Command Center  
- Wake word, STT/TTS polish  
- Auto-start on Windows boot (Scheduled Task)  
- LobsterBoard layout polish  
