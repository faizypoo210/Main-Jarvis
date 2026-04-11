# JARVIS — Agent context map

**Repository root (source of truth for code):** your local clone (do not hardcode machine paths in docs).

This file is the **codebase map** for AI agents (OpenClaw, Cursor, Copilot). **Persona/policy markdown** is edited either live under `%USERPROFILE%\.openclaw\workspace\main\` or as **tracked mirrors** in `config/workspace/` (sync via `scripts/10-sync-openclaw-workspace.ps1`). **Application source** lives in this repo’s code directories.

**LAN / phone access:** set User env `JARVIS_LAN_IP` to this PC’s IPv4; scripts print `http://<IP>:<port>` hints. Do not commit host-specific IPs.

---

## Read order (first session)

| Order | Path | Why |
|-------|------|-----|
| 1 | `context/JARVIS_SPEC.md` | Full system specification |
| 2 | `context/ARCHITECTURE.md` | Data flow and services |
| 3 | `docs/AGENT_CONTEXT.md` | This file — module map and ports |
| 4 | `START_HERE.md` | Cursor-oriented deployment entry |
| 5 | Per-service READMEs | See table below |

---

## Modules (this repo)

| Module | Path | Role |
|--------|------|------|
| **Control plane** | `services/control-plane/` | FastAPI + PostgreSQL: missions, events, approvals, receipts; API key on mutation routes |
| **Command Center** | `services/command-center/` | Vite/React UI (overview, missions, voice WebSocket client) |
| **Voice server** | `voice/` | FastAPI + WebSocket: STT, Ollama, TTS; posts commands to control plane |
| **Coordinator** | `coordinator/` | Stateless: Redis Streams → DashClaw guard → control plane |
| **Executor** | `executor/` | Redis `jarvis.execution` → OpenClaw CLI → receipts / control plane |

---

## Ports (typical defaults in this project)

| Port | Service |
|------|---------|
| **8001** | Control plane HTTP API |
| **8000** | Voice server (HTTP + WebSocket `/ws`) |
| **5173** | Command Center (Vite dev server) |
| **6379** | Redis |
| **5432** | PostgreSQL |
| **18789** | OpenClaw gateway (installed via npm; not in this repo) |

---

## Entry points

| Role | Location |
|------|----------|
| Bring up stack (Windows) | `jarvis.ps1` |
| Control plane ASGI app | `services/control-plane/app/main.py` |
| Voice app | `voice/server.py` |
| Coordinator | `coordinator/coordinator.py` |
| Executor worker | `executor/executor.py` |

---

## Configuration and secrets

- **Never commit** real `.env` files; use `*.env.example` where present.
- **OpenClaw** state: `%USERPROFILE%\.openclaw\` (gateway token, plugins, workspace markdown).
- **DashClaw / API keys:** Windows user environment variables as documented in `README.md`.

---

## Three-way split: code, mirrors, live workspace

| Location | Role |
|----------|------|
| **`F:\Jarvis` (services, coordinator, executor, voice, …)** | **Executable source** — missions and state live in Control Plane + DB |
| **`F:\Jarvis\config\workspace\*.md`** | **Tracked mirrors** of persona/policy files (core: SOUL, AGENTS, TOOLS; optional IDENTITY/USERS). Versioned in git; not authoritative until synced to live |
| **`%USERPROFILE%\.openclaw\workspace\main\`** | **Live** markdown OpenClaw reads at runtime. Update by running `scripts/10-sync-openclaw-workspace.ps1` or edit in place |

**Governance:** Persona/context files shape how models sound; `AGENTS.md` / `TOOLS.md` shape allowed behavior; **mission/control-plane state** remains separate and authoritative (FastAPI + PostgreSQL).

Full detail: [WORKSPACE_SYNC.md](WORKSPACE_SYNC.md), [config/workspace/README.md](../config/workspace/README.md). Model lanes (Ollama vs OpenClaw): [MODEL_LANES.md](MODEL_LANES.md).

---

## Cursor IDE

Open the folder **`F:\Jarvis`** as the workspace so indexing covers the full tree. Project rules live under **`.cursor/rules/`** when present.
