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

---
## Status: READY
## Task: Fix SSE degraded — live updates not connecting

## What it does
Command Center SSE stream shows DEGRADED with 401 Unauthorized.
Vite proxy should inject x-api-key but it is not reaching the control plane correctly.

## What we know already
- Control plane loads CONTROL_PLANE_API_KEY correctly (verified with python -c)
- Vite proxy config reads CONTROL_PLANE_API_KEY (not VITE_ prefix) from .env
- services/command-center/.env has both VITE_CONTROL_PLANE_API_KEY and CONTROL_PLANE_API_KEY
- Proxy test via port 5173 received 140 bytes (stream connected briefly)
- Direct hit to port 8001 with correct key still returned 401 in PowerShell test
  (but that may have been truncated key in test)
- SSE uses fetch not EventSource so headers work

## Hypothesis
Vite dev server process.cwd() may not be services/command-center/ 
when launched from jarvis.ps1, so loadEnv finds wrong .env

## Files to touch
- services/command-center/ (investigate first, then fix)

## Done when
- SSE shows LIVE not DEGRADED in Command Center
- Live updates reconnecting banner disappears

## Next after this
- Voice NLU upgrade