# Housekeeping / stabilization report — closeout register

This document **closes out** the original housekeeping/stabilization findings by mapping each major theme to **fixed**, **partially addressed**, **superseded**, **deferred**, or **out of repo scope**. Evidence points to **in-repo** files, tests, or docs — not chat history.

---

## Register

| Original concern | Current status | Evidence | Notes |
|------------------|----------------|----------|-------|
| **`/api/v1/system/health` runtime error** (undefined locals / incomplete worker registry) | **Fixed** | `services/control-plane/app/api/routes/system.py` builds `worker_registry` via `build_registry_summary`; `services/control-plane/tests/test_api_contracts.py` (`test_api_v1_system_health_includes_worker_registry`) asserts registry + readiness fields | Regression guard with mocked probes |
| **Dead “New Mission” affordance** (nav/button with no action) | **Superseded** | `services/command-center/src/pages/Missions.tsx` states there is no separate new-mission form; missions come from Overview composer / commands. `README.md` documents **shell quick command** + same `POST /api/v1/commands` path | UX consolidated on Overview + global quick command |
| **Synthetic / rehearsal chat “ack” confusion** | **Partially addressed** | Control plane: `rehearsal_mode` / `skip_runtime_publish` in command context (`docs/TESTING.md`, `services/control-plane/tests/test_api_contracts.py`). Operator **inbox** has explicit **acknowledge** via `POST /api/v1/operator/inbox/{item_key}/acknowledge` (`REPO_TRUTH.md`, `app/api/routes/operator.py`) | “Synthetic” is an API contract for tests/scripts, not a user chat mode |
| **Command publish truth / Redis dispatch failure durability** | **Fixed** | `services/control-plane/app/services/command_service.py` emits `runtime_dispatch_succeeded` / `runtime_dispatch_failed` + mission status; `tests/test_api_contracts.py` (`test_command_intake_*`) | Failed publish no longer looks like a healthy pending mission |
| **Executor ACK semantics / silent drop risk** | **Partially addressed** | `executor/executor.py`: `_finish_unexpected_execution_failure` documents **XACK** only after CP acknowledgment or poison-message drop; poison path logs `executor: unexpected_failure_poison_message` | Full liveness proofs are **runtime** concerns; code paths are explicit |
| **Voice cross-session broadcast / wrong TTS to wrong client** | **Partially addressed** | `voice/server.py`: `VoiceConnectionManager` tracks **per-WebSocket** state; `surface_session_id` on connect; `websocket_targets_for_mission` routes mission-scoped fan-out | Ephemeral focus per connection; not a second mission store (`REPO_TRUTH.md`) |
| **Machine-aware health / integrations truth** | **Partially → fixed for workers** | `shared/worker_readiness.py`; `coordinator/coordinator.py` + `executor/executor.py` register `machine_label`, readiness, stream hints; `services/command-center/src/pages/Workers.tsx`, `SystemHealth.tsx`; registry summary counts in `app/services/worker_registry_service.py` | Gateway/Ollama probes still **best-effort** from CP + worker URL hints |
| **Legacy Mission Control branch** | **Deprecated / quarantined** | `README.md`, `DEPLOYMENT_STATUS.md`, `deprecated/mission-control/README.md`, `jarvis.ps1` messages; `JARVIS_INCLUDE_MISSION_CONTROL` = reminder only | **Out of scope** for new features; manual only under `deprecated/` |
| **Control-plane mutation auth** (open or browser-held key confusion) | **Fixed / documented** | `services/control-plane/tests/test_auth_routes.py`; `require_api_key` on mutating routes; `docs/ENV_MATRIX.md` (**dev proxy** adds header server-side; production should proxy — not a normal browser-held secret) | `local_trusted` remains an explicit dev escape hatch |
| **Memory UI read-only gap** | **Fixed** | `services/command-center/src/pages/Memory.tsx` — create / edit / archive / promote flows; `REPO_TRUTH.md` lists `GET/POST /api/v1/operator/memory*` | Governed by same CP auth as other operator writes |
| **Missing global quick command path** | **Fixed** | `services/command-center/src/components/layout/AppShell.tsx` + `QuickCommandPalette.tsx`; `README.md` “shell-level quick command”; `QuickCommandPalette.test.tsx` | Same API as Overview composer |
| **Startup / process truthfulness** (“everything is online”) | **Partially addressed** | `jarvis.ps1` distinguishes HEALTHY vs LISTENING vs **unverified here**; `docs/BRINGUP_RUNBOOK.md`; `scripts/07-verify-jarvis-stack.ps1` stricter gate | **Not** process supervision — see deferred |
| **Worker readiness vs “started/unverified”** | **Fixed (observability)** | Worker metadata `ready_state` / `readiness_reason`; Command Center **Workers** + **System Health** counts; `shared/worker_readiness.py` | `jarvis.ps1` still has **no HTTP probe** for coord/exec — script honesty unchanged; **registry** is the richer signal when workers register |
| **Missing smoke / frontend verification floor** | **Fixed** | `docs/TESTING.md` — `pytest -m unit` vs `-m integration`; `services/command-center` — `npm run test` (Vitest) + `npm run build`; `.github/workflows/ci.yml` | Integration tests still require Postgres (documented) |

---

## What remains intentionally deferred

These are **next-phase** improvements — **not** unfinished items from the original housekeeping sweep:

- **Deeper startup supervision** (supervisord-style restart, OS-level health) — scripts today **start** and **probe** selectively; see `BRINGUP_RUNBOOK.md`.
- **Full session / user auth** for the Command Center — today: **API key** to control plane (and dev-proxy pattern); no end-user login product in-repo.
- **Premium voice / runtime upgrades** — STT/TTS quality, richer flows; voice remains a **parallel surface** to Command Center per `REPO_TRUTH.md`.
- **Routing / model-lane evolution** — `docs/MODEL_LANES.md` vocabulary continues to evolve with OpenClaw; not frozen by this closeout.
- **End-to-end browser automation** (Playwright/Cypress) — not part of the minimal Vitest floor.

---

## How to re-verify quickly

| Layer | Command / doc |
|-------|-----------------|
| Control plane unit tests | `cd services/control-plane && python -m pytest -m unit -q` |
| Control plane integration | `python -m pytest -m integration` (needs Postgres — `docs/TESTING.md`) |
| Command Center tests + build | `cd services/command-center && npm run test && npm run build` |
| Architecture / honesty | `REPO_TRUTH.md`, `docs/ARCHITECTURE_V3.md` |

---

*Last updated as part of the housekeeping report closeout pass.*
