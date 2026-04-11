# JARVIS — AI Command Center

Personal autonomous AI assistant: **Command Center** (operator UI), **Control Plane** (authoritative API), **Voice Server**, **Coordinator** (Redis), **Executor** (OpenClaw CLI), plus OpenClaw Gateway, LobsterBoard, Ollama, Composio, and DashClaw.  
Deployed on Windows 11 (single-machine / LAN dev; see `docs/SECURITY_REVIEW.md`).

## Repo truth (what this codebase actually owns)

Jarvis is **multi-part**, not a single deployable monolith. Before changing behavior or docs, read:

| Doc | Use |
|-----|-----|
| [`docs/ARCHITECTURE_V3.md`](docs/ARCHITECTURE_V3.md) | **Canonical architecture snapshot:** services, boundaries, state, flows, diagrams |
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

The old **openclaw-mission-control** UI (3000/3001) is **deprecated** and not started by default; use Command Center + Control Plane instead.

## Model stack

| Tier | Default | Notes |
|------|---------|--------|
| Local fast | Ollama `qwen3:4b` | Override with `OLLAMA_MODEL` |
| Cloud execution | MiniMax 2.5 via OpenClaw | **Do not hardcode** provider/model slugs in repo; set `JARVIS_OPENCLAW_GATEWAY_MODEL` (or edit `%USERPROFILE%\.openclaw\openclaw.json`) per your OpenClaw + MiniMax profile |

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

Optional: deprecated **openclaw-mission-control** (3000/3001) is **not** started by default. Set User env `JARVIS_INCLUDE_MISSION_CONTROL=1` before `jarvis.ps1` only if you still need that UI.

Primary URLs after start:

- Command Center: http://localhost:5173  
- Control Plane API: http://localhost:8001  
- Voice Server: http://localhost:8000  

## Deployment phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Docker + PostgreSQL + Redis | Complete |
| 2 | Legacy openclaw-mission-control (optional) | Skipped by default |
| 3 | OpenClaw Gateway | Complete |
| 4 | LobsterBoard dashboard | Complete |
| 5 | Ollama + `qwen3:4b` | Complete |
| 6 | Composio integrations | Complete |
| 7 | Firewall + phone access | Complete |
| 8 | E2E testing | In progress |

## Secrets

All secrets live in **Windows User environment variables** and **`%USERPROFILE%\.openclaw\`** — never committed. **Rotation checklist:** [`docs/SECRET_ROTATION.md`](docs/SECRET_ROTATION.md). **Trust model:** [`docs/SECURITY_REVIEW.md`](docs/SECURITY_REVIEW.md).

Examples (set only what your providers require; names follow OpenClaw / vendor docs):

- Composio: `COMPOSIO_API_KEY`  
- OpenClaw gateway token: set **`JARVIS_OPENCLAW_GATEWAY_TOKEN`** before `scripts/03-configure-openclaw.ps1`, or edit `%USERPROFILE%\.openclaw\openclaw.json` manually (never commit)  
- Control plane: `CONTROL_PLANE_API_KEY` (must match `services/control-plane/.env`)  
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

## Roadmap

- Phase 8: E2E testing against Control Plane + Command Center  
- Wake word, STT/TTS polish  
- Auto-start on Windows boot (Scheduled Task)  
- LobsterBoard layout polish  
