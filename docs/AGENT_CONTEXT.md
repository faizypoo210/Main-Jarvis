# JARVIS — Agent context map

**Repository root (source of truth for code):** `F:\Jarvis`  
**Typical LAN IP for this machine:** `10.0.0.249` (service URLs often use this host).

This file is the **codebase map** for AI agents (OpenClaw, Cursor, Copilot). Policy and persona live in `%USERPROFILE%\.openclaw\workspace\main\` (SOUL, AGENTS, TOOLS, etc.); **application source** lives **only** under `F:\Jarvis`.

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

## OpenClaw workspace vs this repository

| Location | Contents |
|----------|----------|
| `%USERPROFILE%\.openclaw\workspace\main\` | SOUL, AGENTS, IDENTITY, TOOLS, USERS — **policy and identity** |
| `F:\Jarvis\config\workspace\` | Optional **tracked snippets** / mirrors; not a substitute for the live `.openclaw` workspace |
| **`F:\Jarvis` (git repo)** | **All executable code and infra scripts** |

When changing **behavior**, edit files under **`F:\Jarvis`**. When changing **operator policy or persona**, edit the files under **`.openclaw\workspace\main\`** (and keep any repo copies in sync if you use them).

---

## Cursor IDE

Open the folder **`F:\Jarvis`** as the workspace so indexing covers the full tree. Project rules live under **`.cursor/rules/`** when present.
