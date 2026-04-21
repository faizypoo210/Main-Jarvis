# CURRENT TASK

---

## [DONE] Executor worker
Built executor/worker.py — Ollama intent classification, webbrowser.open, jarvis.receipts

## [DONE] Tray stop fix
Already implemented correctly, no change needed

## [DONE] Command Center three-zone layout
Three zones, /missions default, receipts page, health stats sidebar

## [DONE] Wire missions data
Already wired, fixed REPO_MAP.md paths only

## [DONE] Process supervision / watchdog
scripts/watchdog.ps1 — cooldown, lockfile, teardown, auto-restart

## [DONE] Fix voice server launch command
jarvis.ps1 and watchdog.ps1 updated to use voice.server:app from repo root

## [DONE] docker-compose.yml
jarvis-postgres and jarvis-redis with named volume, correct credentials, jarvis-net network

## [DONE] One-click startup and shutdown
jarvis-start.bat and jarvis-stop.bat at repo root

## [DONE] Wire tray stop button to jarvis-stop.bat
tray/tray.pyw calls jarvis-stop.bat, icon.stop() after, isfile guard added

## [DONE] Fix SSE degraded
Set VITE_CONTROL_PLANE_URL empty, fixed vite.config.ts loadEnv path

## [DONE] OpenClaw gateway + Ollama health
Added JARVIS_HEALTH_OPENCLAW_GATEWAY_URL and JARVIS_HEALTH_OLLAMA_URL to control plane .env

## [DONE] Voice NLU upgrade
Added Ollama intent classification to voice/server.py before post_voice_intake

## [DONE]: Alembic startup cleanup
Migrations always run on startup


## [DONE]: Testing Campaign, Slice 2 Fix
All 8 test slices passed. Core Jarvis stack is verified end-to-end

## What we are doing
Systematic testing of all Jarvis functions.

# CURRENT_TASK

## Status: ACTIVE — Post-testing known issue resolution

## Completed
All 8 test slices passed. Core Jarvis stack is verified end-to-end.
# CURRENT TASK


## [DONE] All previous slices + post-testing issue resolution
Full stack verified. Executor, watchdog, voice NLU, SSE, one-click start/stop — all shipped and committed.

---

# CURRENT_TASK

## Status: ACTIVE — Architecture pass

---

## Slice A — Lock model roles in env [NEXT]
**Goal:** Eliminate all hardcoded model strings. Single source of truth in .env.
**Vars to add:** JARVIS_LOCAL_MODEL=qwen3.5:4b, JARVIS_CLOUD_MODEL=minimax-2.5
**Files:** .env, voice/server.py, executor/executor.py
**Not touching:** control plane, coordinator, frontend
**Verify:** `grep -rn "qwen\|minimax\|phi4" voice/ executor/` returns zero literals.

## Slice B — Shared Jarvis reply synthesis module
**Goal:** Voice and Command Center use the same reply logic. One Jarvis voice across surfaces.
**Files:** new shared/reply.py, voice/server.py (import + call)
**Not touching:** control plane, executor, frontend
**Verify:** Voice TTS copy is Jarvis-voiced, not raw Ollama output.

## Slice C — Runtime truth panel in Command Center
**Goal:** UI shows active models, lane routing, and real worker status — not inferred.
**Files:** services/command-center/src/pages/SystemHealth.tsx (or equivalent)
**Not touching:** all backend services
**Verify:** System Health shows Runtime card: local model, cloud model, executor status, coordinator status.

---

## Slice tracker

| # | Name | Status |
|---|------|--------|
| All previous | Full stack + testing campaign | ✅ DONE |
| Slice A | Model role env lock | 🔧 ACTIVE |
| Slice B | Shared reply synthesis | ⏳ QUEUED |
| Slice C | Runtime truth UI panel | ⏳ QUEUED |

---

## Key env / credentials
- CONTROL_PLANE_API_KEY=J9qBeIin1yWlWIMZfB/0pCNXmTnHfZtLZFBO+BoYcpY=
- REDIS_URL=redis://localhost:6379
- JARVIS_LOCAL_MODEL=qwen3.5:4b
- JARVIS_CLOUD_MODEL=minimax-2.5
- OLLAMA_TIMEOUT_SEC=120