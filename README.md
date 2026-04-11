# JARVIS — AI Command Center

Personal autonomous AI assistant: **Command Center** (operator UI), **Control Plane** (authoritative API), **Voice Server**, **Coordinator** (Redis), **Executor** (OpenClaw CLI), plus OpenClaw Gateway, LobsterBoard, Ollama, Composio, and DashClaw.  
Deployed on Windows 11 (10.0.0.249).

## Canonical architecture

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
- Local IP: 10.0.0.249  
- Services on home WiFi: `http://10.0.0.249:<port>`

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

All secrets live in **Windows User environment variables** and **`%USERPROFILE%\.openclaw\`** — never committed.

Examples (set only what your providers require; names follow OpenClaw / vendor docs):

- Composio: `COMPOSIO_API_KEY`  
- OpenClaw gateway token: in `%USERPROFILE%\.openclaw\openclaw.json` (or set `JARVIS_OPENCLAW_GATEWAY_TOKEN` before running configure scripts — see script comments)  
- MiniMax / other cloud providers: configure via OpenClaw **`auth-profiles.json`** and env vars **per OpenClaw documentation** (not hardcoded here)

Config files with secrets (not in repo):

- `%USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json`  
- Deprecated UI only: `C:\projects\openclaw-mission-control\` `.env` if you still run that stack

## OpenClaw workspace (persona vs code)

| What | Where |
|------|--------|
| **Executable source** | This repo (`services/`, `coordinator/`, `executor/`, …) |
| **Tracked markdown mirrors** | `config/workspace/` (`SOUL.md`, `AGENTS.md`, `TOOLS.md`; add `IDENTITY.md` / `USERS.md` when ready) |
| **Live files OpenClaw reads** | `%USERPROFILE%\.openclaw\workspace\main\` (sync with `scripts/10-sync-openclaw-workspace.ps1`) |
| **Mission state (authoritative)** | Control Plane API + PostgreSQL — not in workspace markdown |

See [docs/WORKSPACE_SYNC.md](docs/WORKSPACE_SYNC.md) and [config/workspace/README.md](config/workspace/README.md).

## Architecture

See [context/ARCHITECTURE.md](context/ARCHITECTURE.md) for service map and data flow.  
See [context/JARVIS_SPEC.md](context/JARVIS_SPEC.md) for the broader system specification.

## Roadmap

- Phase 8: E2E testing against Control Plane + Command Center  
- Wake word, STT/TTS polish  
- Auto-start on Windows boot (Scheduled Task)  
- LobsterBoard layout polish  
