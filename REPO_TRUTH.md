# Repo truth (Main-Jarvis)

This file is the **honesty contract** for the `faizypoo210/Main-Jarvis` repository: what is owned here, what is not, and how to verify claims. Prefer this over assumptions from chat history or stale UI copy.

## Purpose

Jarvis is a **layered** system: a **governed control plane** (missions, timeline events, approvals, receipts, realtime updates) plus **execution**, **coordination**, **operator UI**, and **voice**—with **OpenClaw**, **Redis**, **PostgreSQL**, and **machine-local** configuration living at known boundaries. This repo holds the application code and scripts for that stack; it does **not** replace vendor installers, cloud accounts, or files under `%USERPROFILE%\.openclaw\` unless explicitly synced from tracked mirrors.

## Repo ownership (in-repo)

| Concern | Where truth lives in git |
|--------|---------------------------|
| Control Plane HTTP API and persistence | `services/control-plane/` (FastAPI, Alembic, PostgreSQL) |
| Operator web UI | `services/command-center/` (React/Vite) |
| Redis → policy → control plane bridging | `coordinator/` |
| `jarvis.execution` → OpenClaw → receipts | `executor/` |
| Voice STT/TTS and control-plane/Redis integration | `voice/` |
| Workspace persona/policy **mirrors** (not mission state) | `config/workspace/` — see **`docs/OPENCLAW_WORKSPACE_FILES.md`** for **SOUL / AGENTS / TOOLS / …** roles |
| Deployment, smoke, golden-path, benchmark scripts | `scripts/` |
| High-level architecture and spec narrative | `context/ARCHITECTURE.md`, `context/JARVIS_SPEC.md` |
| Operational docs (security, sync, evals, lanes) | `docs/` |

Authoritative **mission state** (status, events, approvals, receipts) is **not** in workspace markdown; it is in the **control plane database**, accessed via the API.

## Major mechanisms (crucial for full context)

These are the **non-negotiable mechanisms** to understand Jarvis end-to-end. The GitHub repo **does** contain code and docs for each; it **does not** duplicate your full **machine-local OpenClaw** tree (gateway config, auth profiles, live workspace). Together, **repo + your `%USERPROFILE%\.openclaw\` setup** is the full runtime picture.

| Mechanism | What it does | Represented in repo as | Not in repo (typical) |
|-----------|----------------|-------------------------|------------------------|
| **Mission authority** | Single source of truth for missions, timeline events, approvals, receipts, SSE | `services/control-plane/`, Alembic, `docs/GOLDEN_PATH.md` | Your PostgreSQL data |
| **Operator UI** | Browse missions, act on approvals, mission detail, live updates | `services/command-center/` | N/A |
| **Command intake** | Create missions from text + surface metadata | `POST /api/v1/commands`, `app/schemas/commands.py` | — |
| **Redis coordination** | Stream-based handoff between services | Stream names in `coordinator/coordinator.py`, `executor/executor.py`, `voice/server.py` | Redis persistence / Docker volume |
| **Governance bridge** | Policy via DashClaw → control plane + streams | `coordinator/` | DashClaw deployment URL, `DASHCLAW_API_KEY` |
| **Execution plane** | Work off `jarvis.execution`, run agent via OpenClaw, post receipts | `executor/` | **OpenClaw CLI install**, **gateway process**, **`openclaw.json`**, **`auth-profiles.json`**, provider accounts |
| **OpenClaw agent layer** | Models, tools, **persona/policy markdown** (`SOUL`, `AGENTS`, `TOOLS`, optional `IDENTITY`/`USERS`/`MEMORY`) the gateway reads | **Mirrors + sync:** `config/workspace/`, `scripts/10-sync-openclaw-workspace.ps1`, `docs/OPENCLAW_WORKSPACE_FILES.md`, `docs/WORKSPACE_SYNC.md` | **Live** `%USERPROFILE%\.openclaw\workspace\main\`; **`openclaw.json`**, **`auth-profiles.json`**, plugins—never fully in git |
| **Voice path** | STT/TTS and forwarding toward control plane / streams | `voice/` | Whisper/GPU env, local `.env` beside `server.py` |
| **Verification** | Prove API and optional live stack | `scripts/13-rehearse-golden-path.ps1`, `14-rehearse-live-stack.ps1`, `docs/LIVE_STACK_REHEARSAL.md` | Your machine’s services all up |

**How to read “OpenClaw” in this project:** the **executor** and **workspace sync** are first-class **in-repo** mechanisms. The **gateway runtime and credentials** are **machine-local**—documented in `MACHINE_SETUP_STATUS.md` and `docs/MODEL_LANES.md`, not copied into git.

## What this repo does not own

- **OpenClaw Gateway** runtime, global CLI install path, and live `openclaw.json` / `auth-profiles.json` (machine-local; see `MACHINE_SETUP_STATUS.md`).
- **LobsterBoard** and **openclaw-mission-control** codebases (separate clones under paths described in `DEPLOYMENT_STATUS.md` / README; optional/deprecated where noted).
- **Provider keys** (Composio, MiniMax, cloud LLMs): configured per vendor docs and OpenClaw, not committed here.
- **Production deployment** of your network, firewall, DNS, or tunnels—scripts assist; they are not a hosted product.

## External / upstream dependencies

- **PostgreSQL** and **Redis** (typically Docker per `jarvis.ps1` / deployment docs).
- **OpenClaw** CLI and gateway for executor-driven agent runs.
- **Ollama** (optional local fast lane) when used by voice or via OpenClaw model strings.
- **DashClaw** when used by the coordinator for guard/outcomes (env-configured base URL + API key).
- **Composio** and other integrations when enabled in OpenClaw workspace and tooling.

## Machine-local truth (outside git)

Secrets, gateway model selection, OAuth tokens, LAN IP, and the **live** OpenClaw tree under `%USERPROFILE%\.openclaw\` are **not** reproducible from clone alone. Tracked mirrors under `config/workspace/` (**`SOUL.md`**, **`AGENTS.md`**, **`TOOLS.md`**, optional **`IDENTITY.md` / `USERS.md`**, optional **`MEMORY.md`**) are the **versioned** representation of **agent persona and policy**; you still run **`10-sync-openclaw-workspace.ps1`** (or edit live and copy back) so the gateway sees updates. See **`docs/OPENCLAW_WORKSPACE_FILES.md`** for a file-by-file map. Tracked mirrors are **not** the control plane.

See **`MACHINE_SETUP_STATUS.md`** for a practical checklist.

## State and authority boundaries

| Layer | Authority |
|-------|-----------|
| Mission lifecycle, approvals, receipts, SSE feed | **Control Plane** API + DB |
| Execution of delegated work after routing | **Executor** + OpenClaw (posts receipts **to** control plane) |
| Policy / guard / outcomes (when coordinator path used) | **DashClaw** (coordinator calls it; results persisted via control plane) |
| Operator narrative and drill-down | **Command Center** (reads APIs; does not define mission truth) |
| Persona / markdown context | **Workspace files** (synced mirrors + live OpenClaw dir) |

## Reality labels (used in code comments)

| Label | Meaning |
|-------|---------|
| `PLACEHOLDER:` | UI or script shell exists; end-to-end product behavior is not implemented or not wired. |
| `PARTIAL:` | Some paths work; others are stubbed, schema-only, or need integration work. |
| `MACHINE_CONFIG_REQUIRED:` | Behavior depends on env, auth files, or services outside the repo. |
| `UPSTREAM_DEPENDENCY:` | Correctness depends on an external tool, API, or versioned behavior not pinned here. |
| `TRUTH_SOURCE:` | This file or module defines or mirrors a contract others must align with. |

## Verification sources

| Claim | How to verify |
|-------|----------------|
| Control plane healthy | `GET /health` on port **8001** (see README) |
| API governance loop | `docs/GOLDEN_PATH.md` + `scripts/13-rehearse-golden-path.ps1` |
| Full execution chain | `docs/LIVE_STACK_REHEARSAL.md` + `scripts/14-rehearse-live-stack.ps1` |
| Command Center build | `cd services/command-center && npm run build` |
| Broader deployment phases | `DEPLOYMENT_STATUS.md`, `docs/E2E_SMOKE_TEST.md` |

## Known limitations

- **Command Center** routes such as **Integrations**, **Workers**, **Cost & Usage**, and **System Health** are **placeholder pages** (see `App.tsx`). **Activity** is a minimal stub until a unified feed exists.
- **Control Plane** includes DB models for workers, integrations, and cost events; **not all** of these have first-class HTTP surfaces in the current API tree—treat as **partial** until routes exist (see `STATUS.md`).
- **Coordinator** and **executor** require correct env and Redis stream consumers; misconfiguration surfaces as silent stalls or errors in logs, not as compile-time failures.

For a feature-level ledger, see **`STATUS.md`**. For boxes-and-arrows, see **`SYSTEM_MAP.md`**.
