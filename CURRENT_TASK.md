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

## [DONE] Alembic startup cleanup
Migrations always run on startup

## [DONE] Testing Campaign + post-testing issue resolution
All 8 test slices passed. Core Jarvis stack verified end-to-end. Executor, watchdog, voice NLU, SSE, one-click start/stop — all shipped and committed.

## [DONE] Architecture pass
Model env vars locked, SOUL.md persona wired, shared/reply.py stub in place, runtime truth panel in Command Center.

---

## [DONE] Slice 1 — Wire global Receipts page
Already implemented. Receipts.test.tsx committed.
**Goal:** Replace Receipts.tsx PLACEHOLDER_ROWS with a real list backed by new GET /api/v1/receipts endpoint.
**Files:**
- services/control-plane/app/api/routes/receipts.py
- services/command-center/src/pages/Receipts.tsx
- services/command-center/src/lib/api.ts
**Not touching:** voice, executor, coordinator, control plane models, mission schema
**Verify:** Live executor run → receipt appears in /receipts list. Vitest empty-state test passes.

## [DONE] Slice 2 — Jarvis reply service
Ollama qwen3.5:4b local brain. think:false for fast replies. config.py absolute .env path fix.
**Goal:** New POST /api/v1/jarvis/reply composes (user text + mission context + pending approvals + recent receipts + persona from SOUL.md) into a Jarvis-voiced reply string. Voice server and Command Center chat both consume it.
**Files:**
- new services/control-plane/app/services/jarvis_reply.py
- new route in services/control-plane/app/api/routes/
- voice/server.py (consume instead of current stub)
- services/command-center/src/components/conversation/ConversationThread.tsx (render Jarvis reply bubbles)
**Not touching:** executor, coordinator, mission schema, Alembic migrations
**Verify:** Chat "what's going on?" → Jarvis-voiced summary naming active missions and pending approvals. Voice same question → same content spoken.

## [DONE] Slice 3 — Cloud lane dispatch (MiniMax 2.5)
**Goal:** Make requested_lane=="gateway" actually route to MiniMax 2.5 via existing OpenClaw auth profile. Receipt lane_truth must show openclaw_model_lane: gateway on a cloud run.
**Files:**
- executor/executor.py
- shared/routing.py
- shared/lane_truth.py
**Not touching:** control plane, frontend, coordinator
**Verify:** scripts/11-smoke-model-lanes.ps1 with gateway-routed prompt → receipt shows cloud model id.

## [DONE] Slice 4 — Memory retrieval into replies
get_top_k_memory: substring + importance + recency. Injected into jarvis reply prompt.
**Goal:** Reply service loads top-K relevant memory_items into context before calling LLM. v1 = substring match + memory_type filter + recency sort. No embeddings.
**Files:**
- services/control-plane/app/services/jarvis_reply.py
- services/control-plane/app/services/memory_service.py (new query helper)
**Not touching:** voice server, frontend, executor, coordinator
**Verify:** Promote a mission to memory → ask a related question → Jarvis reply references it.

## [NEXT] Slice 5 — Mission decomposition v1
**Goal:** Planner service generates a linear stage list for complex missions and writes stages[] before execution. Executor runs stages sequentially, each emitting its own receipt. No branching, no parallel workers.
**Files:**
- new services/control-plane/app/services/mission_planner.py
- services/control-plane/app/api/routes/missions.py (accept stage writes)
- executor/executor.py (consume stages)
**Not touching:** voice, frontend, coordinator contract
**Verify:** "Research top 5 Polymarket arb opportunities and save them" decomposes into 3–5 stages, each stage emits a receipt, mission completes with structured output.