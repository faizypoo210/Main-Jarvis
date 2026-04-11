# Repo truth (Main-Jarvis)

This file is the **honesty contract** for the `faizypoo210/Main-Jarvis` repository: what is owned here, what is not, and how to verify claims. Prefer this over assumptions from chat history or stale UI copy.

## Purpose

Jarvis is a **layered** system: a **governed control plane** (missions, timeline events, approvals, receipts, realtime updates, **durable operator memory**) plus **execution**, **coordination**, **operator UI**, and **voice**—with **OpenClaw**, **Redis**, **PostgreSQL**, and **machine-local** configuration living at known boundaries. **Mission state** (missions + mission-scoped events) is not the same as **memory state** (`memory_items`): memory is long-lived operator context, not a dump of chat or mission logs. This repo holds the application code and scripts for that stack; it does **not** replace vendor installers, cloud accounts, or files under `%USERPROFILE%\.openclaw\` unless explicitly synced from tracked mirrors.

## Repo ownership (in-repo)

| Concern | Where truth lives in git |
|--------|---------------------------|
| Control Plane HTTP API and persistence | `services/control-plane/` (FastAPI, Alembic, PostgreSQL) — includes **`memory_items`** for operator durable memory; **approval review bundles** — `GET /api/v1/approvals/{approval_id}/bundle` (`app/services/approval_review_packet.py`, `app/schemas/approval_bundle.py`) |
| Operator web UI | `services/command-center/` (React/Vite) |
| Redis → policy → control plane bridging | `coordinator/` |
| `jarvis.execution` → OpenClaw → receipts | `executor/` |
| Voice STT/TTS and control-plane/Redis integration | `voice/` — approval list/readout/decision via `approval_voice.py` (`decided_via: voice`); not a second mission store |
| Workspace persona/policy **mirrors** (not mission state) | `config/workspace/` — **`governance-manifest.json`** defines the canonical file set; **`docs/OPENCLAW_WORKSPACE_FILES.md`** explains roles vs control plane |
| **GitHub issue + draft PR + PR merge workflows** | Approval + REST in control plane | `github_issue_workflow.py`, `github_pr_workflow.py`, `github_pr_merge_workflow.py`, `docs/INTEGRATIONS_GITHUB.md` | **Not** Composio/OpenClaw; **`JARVIS_GITHUB_TOKEN`**; merge is **preflight + merge existing PR only** |
| **Gmail create-draft + reply-draft + send-draft workflows** | Approval + Gmail API `messages.get` (metadata for reply) + `drafts.create` / `drafts.send` via control plane | `app/services/gmail_draft_workflow.py`, `app/integrations/gmail_adapter.py`, `docs/INTEGRATIONS_GMAIL.md` | **Not** inbox listing or polling; **reply-draft** is **one** referenced thread/message; **send** is **existing draft id only**; requires **`JARVIS_GMAIL_*`**; send needs OAuth scope **`gmail.send`** (see doc) |
| Deployment, smoke, golden-path, benchmark scripts | `scripts/` |
| High-level architecture and spec narrative | `context/ARCHITECTURE.md`, `context/JARVIS_SPEC.md` |
| Operational docs (security, sync, evals, lanes) | `docs/` |

Authoritative **mission state** (status, events, approvals, receipts) is **not** in workspace markdown; it is in the **control plane database**, accessed via the API.

## Major mechanisms (crucial for full context)

These are the **non-negotiable mechanisms** to understand Jarvis end-to-end. The GitHub repo **does** contain code and docs for each; it **does not** duplicate your full **machine-local OpenClaw** tree (gateway config, auth profiles, live workspace). Together, **repo + your `%USERPROFILE%\.openclaw\` setup** is the full runtime picture.

| Mechanism | What it does | Represented in repo as | Not in repo (typical) |
|-----------|----------------|-------------------------|------------------------|
| **Mission authority** | Single source of truth for missions, timeline events, approvals, receipts, SSE | `services/control-plane/`, Alembic, `docs/GOLDEN_PATH.md` | Your PostgreSQL data |
| **Durable operator memory** | Long-lived `memory_items` rows + mission timeline hooks (`memory_saved` / `memory_promoted` / `memory_archived`) when tied to a mission | `app/models/memory_item.py`, `app/services/memory_service.py`, `app/services/memory_promotion.py`, `GET/POST /api/v1/operator/memory*` | **Not** automatic extraction from every command; **not** full receipt/chat ingest (see promotion rules in code) |
| **Heartbeat supervision (v1)** | Periodic explicit rule checks; **deduped** open/resolved rows in `heartbeat_findings`; no chat or LLM “nudges” | `app/services/heartbeat_service.py`, `heartbeat/heartbeat.py` worker, `GET /api/v1/operator/heartbeat`, Activity category `heartbeat` | **Not** live OS process monitoring; worker staleness uses `workers.last_heartbeat_at` only; thresholds via `HEARTBEAT_*` env (see `services/control-plane/.env.example`) |
| **Operator UI** | Browse missions, act on approvals (including **packet-based review** on `/approvals`), mission detail, live updates | `services/command-center/` | N/A |
| **Command intake** | Create missions from text + surface metadata | `POST /api/v1/commands`, `app/schemas/commands.py` | — |
| **Redis coordination** | Stream-based handoff between services; mission execution payloads carry compact **routing** metadata (`requested_lane` / `actual_lane` / fallback) | Stream names in `coordinator/coordinator.py`, `executor/executor.py`, `voice/server.py`; routing heuristics in `shared/routing.py` | Redis persistence / Docker volume; **no** separate local-fast mission executor beyond OpenClaw |
| **Governance bridge** | Policy via DashClaw → control plane + streams | `coordinator/` | DashClaw deployment URL, `DASHCLAW_API_KEY` |
| **Execution plane** | Work off `jarvis.execution`, run agent via OpenClaw, post receipts | `executor/` | **OpenClaw CLI install**, **gateway process**, **`openclaw.json`**, **`auth-profiles.json`**, provider accounts |
| **OpenClaw agent layer** | Models, tools, **persona/policy markdown** (`SOUL`, `IDENTITY`, `USERS`, `AGENTS`, `MEMORY`, `HEARTBEAT`, `TOOLS`) the gateway reads after sync | **Mirrors + manifest + sync + audit:** `config/workspace/governance-manifest.json`, `scripts/10-sync-openclaw-workspace.ps1`, `scripts/11-audit-workspace-governance.ps1`, `docs/OPENCLAW_WORKSPACE_FILES.md` | **Live** `%USERPROFILE%\.openclaw\workspace\main\`; **`openclaw.json`**, **`auth-profiles.json`**, plugins—never fully in git |
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

Secrets, gateway model selection, OAuth tokens, LAN IP, and the **live** OpenClaw tree under `%USERPROFILE%\.openclaw\` are **not** reproducible from clone alone. Tracked mirrors under `config/workspace/` (see **`governance-manifest.json`**) are the **versioned** representation of **agent persona and policy** for the local gateway; run **`10-sync-openclaw-workspace.ps1`** and **`11-audit-workspace-governance.ps1`** (or edit live and copy back). **`USERS.md`** is the canonical operator file name (**not** `USER.md`). See **`docs/OPENCLAW_WORKSPACE_FILES.md`**. Tracked mirrors are **not** the control plane.

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
| Approval review packet (bundle) | `GET /api/v1/approvals/{approval_id}/bundle` (read-only; no secrets in normalized fields); Command Center `/approvals` |
| Phase 8 deployment report | `scripts/08-final-report.ps1` writes `docs/08-deployment-report.txt` (core: operator smoke + workspace audit; external OAuth probes skip or fail honestly). **Not** a substitute for live E2E (`09-smoke-test-e2e.ps1`). |
| Heartbeat open findings | `GET /api/v1/operator/heartbeat` (same session as other operator routes) |
| Heartbeat run (API key) | `POST /api/v1/heartbeat/run` with `x-api-key`; or run `python heartbeat/heartbeat.py` with `CONTROL_PLANE_URL`, `CONTROL_PLANE_API_KEY`, `HEARTBEAT_INTERVAL_SEC` |
| Workspace pack audit | `.\scripts\11-audit-workspace-governance.ps1` from repo root |
| Workspace sync to OpenClaw | `.\scripts\10-sync-openclaw-workspace.ps1` |
| GitHub issue + draft PR workflows | `docs/INTEGRATIONS_GITHUB.md`; APIs under `.../integrations/github/create-issue` and `.../create-pull-request` |
| Gmail draft + send-draft workflows | `docs/INTEGRATIONS_GMAIL.md`; APIs under `/api/v1/missions/.../integrations/gmail/create-draft` and `.../send-draft` |
| Operator Value Evals v1 | `GET /api/v1/operator/evals`, `docs/OPERATOR_EVALS.md` (metric definitions), Command Center `/evals`, `scripts/18-run-operator-value-evals.ps1` | **Operational** aggregates from DB truth — not subjective scoring |
| Broader deployment phases | `DEPLOYMENT_STATUS.md`, `docs/E2E_SMOKE_TEST.md` |

## Known limitations

- **Command Center** exposes **Integrations**, **Workers**, **Cost & Usage**, **System Health**, and **Activity** as **API-backed** operator pages. Integrations shows **readiness and honesty signals** from `GET /api/v1/operator/integrations` (DB rows + safe machine/repo probes); it does **not** perform OAuth or store vendor tokens. **Governed GitHub issue/PR workflows** are separate control-plane APIs (`docs/INTEGRATIONS_GITHUB.md`), not that hub page.
- **OpenClaw workspace markdown** (`config/workspace/`) shapes **local** model/runtime behavior after sync; it is **not** an authority layer over missions or approvals—those remain in the **control plane**.
- **Control Plane** includes DB models for workers and cost events; **first-class REST CRUD** for those domains may still be incomplete—operator routes under `/api/v1/operator/*` and `/api/v1/system/health` are **read-only** aggregates (see `STATUS.md`).
- **Coordinator** and **executor** require correct env and Redis stream consumers; misconfiguration surfaces as silent stalls or errors in logs, not as compile-time failures.

For a feature-level ledger, see **`STATUS.md`**. For boxes-and-arrows, see **`SYSTEM_MAP.md`**.
