# JARVIS Architecture

For **repo ownership, placeholders, and verification commands**, see also the root **`REPO_TRUTH.md`**, **`SYSTEM_MAP.md`**, **`STATUS.md`**, and **`MACHINE_SETUP_STATUS.md`**. This file stays a short operational map; those files are the honesty ledger.

## Authority and UI

- **Control Plane** (`http://localhost:8001`, FastAPI) is the **authoritative** store for missions, commands, approvals, and receipts.  
- **Command Center** (`http://localhost:5173`, React/Vite) is the **primary operator UI**.  
- **Voice Server** (`http://localhost:8000`) handles realtime audio, STT/TTS, and forwards intent to the control plane / Redis.  
- **Legacy openclaw-mission-control** (3000/3001) is deprecated; not started by default. Do not use it as authority (use Command Center + Control Plane).

## Data flow (high level)

```
Operator / phone / browser
    → Command Center (5173)  ──HTTP──►  Control Plane (8001)
    → Voice Server (8000)    ──WS/API►  Control Plane + Redis
    → LobsterBoard (8080)   ──supplemental dashboards / widgets only

OpenClaw Gateway (18789)  ◄── agent / tool execution (Executor uses OpenClaw CLI)

Coordinator (stateless)   ◄── Redis (6379) streams  ──► Control Plane

PostgreSQL (5432)  ◄── persistence ◄── Control Plane
```

## Redis and execution

- **Coordinator** routes stream events (e.g. `jarvis.commands`) and does not own business state.  
- **Executor** consumes `jarvis.execution`, invokes **OpenClaw CLI** against the gateway, and posts **receipts** back to the control plane.

## Local vs cloud models

- **Local fast path:** Ollama on **11434**, default model **`qwen3:4b`** (env `OLLAMA_MODEL`).  
- **Cloud execution:** MiniMax 2.5 (and similar) via **OpenClaw** — provider and model id are **configured in OpenClaw** (`openclaw.json` / auth profiles), not hardcoded in this repo.

## Approval flow (when DashClaw / LobsterBoard are used)

OpenClaw or the control plane may request human approval → DashClaw risk → LobsterBoard / Command Center → approve → execution continues.

## Container layout

**Host / Docker**

- `jarvis-postgres`, `jarvis-redis` (Docker)

**Processes (typical)**

- Control Plane, Command Center (`npm run dev`), Voice Server, Coordinator, Executor  
- OpenClaw Gateway, Ollama, LobsterBoard  
- Optional: deprecated openclaw-mission-control (3000/3001) — bring up manually from `deprecated/mission-control/`; `jarvis.ps1` does not start it (`JARVIS_INCLUDE_MISSION_CONTROL=1` prints a deprecation reminder only)
