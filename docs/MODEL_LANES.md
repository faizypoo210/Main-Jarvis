# Model lanes (canonical truth)

> **Truth boundary:** model lane choice does **not** move mission authority off the control plane. For ownership and machine config, see [`../REPO_TRUTH.md`](../REPO_TRUTH.md) and [`../MACHINE_SETUP_STATUS.md`](../MACHINE_SETUP_STATUS.md).

This document is the **single operator-facing definition** of lane-related terms. Prefer it over ad hoc UI copy.

## Canonical lane truth model (v1)

| Field | Where it lives | Meaning |
|-------|----------------|--------|
| **requested_lane** | `routing_decided` payload, `execution_meta.routing`, `execution_meta.lane_truth` | Classifier intent: `local_fast` or `gateway` (heuristic over command text + risk). |
| **routing_actual_lane** | Same (stored as `actual_lane` in routing payloads) | Mission **execution path class** for `jarvis.execution`: today always **`gateway`** because the only consumer is the OpenClaw executor. **Not** the same as “local Ollama direct.” |
| **fallback_applied** | Same | `true` when `requested_lane` was `local_fast` but the mission path is still the OpenClaw executor (`actual_lane` `gateway`). |
| **reason_code** / **reason_summary** | Same | Stable machine-readable code + short human line (e.g. `MISSION_EXECUTOR_GATEWAY_ONLY` when fallback). |
| **fallback_reason_code** | Same | When `fallback_applied`, equals the stable code explaining the fallback (same family as `reason_code` in v1). `null` when no fallback. |
| **openclaw_model_lane** | `execution_meta` | **OpenClaw default agent model** target: `local` if model id starts with `ollama/`, else `gateway` (cloud/other). Still goes **through** OpenClaw CLI — not direct Ollama from the executor process. |
| **mission_execution_path** | `execution_meta` | Always **`openclaw_executor`** for missions in this repo: there is no separate local-fast mission worker. |
| **lane_truth** | `execution_meta` | Small JSON block (`schema_version` `1`) reconciling **routing snapshot** + **openclaw_model_lane** on the receipt so operators can compare without guessing. |

### Direct vs derived

- **Direct from stored events:** `routing_decided` rows (mission_events).
- **Direct from executor receipt:** `execution_meta` on `openclaw_execution` receipts (and mirrored on `receipt_recorded` timeline events).
- **Derived for display:** Evals aggregates (counts, match/mismatch); Activity titles; Command Center compact lines — all **read** the above, they do not invent lanes.

### What “local” means (avoid confusion)

| Phrase | Meaning |
|--------|--------|
| **local_fast** (requested) | “Prefer low-latency local style” from the **router** — does **not** imply a local mission executor exists. |
| **openclaw_model_lane = local** | Gateway’s default model is an **`ollama/...`** id — execution still flows **OpenClaw → gateway → Ollama**. |
| **Voice direct Ollama** | Voice server may call Ollama **HTTP** for acks — **no** `routing_decided` and **no** executor receipt. See [Voice vs mission](#voice-vs-mission-execution) below. |

## Roles (capabilities)

| Capability | Typical runtime | Mission authority |
|------------|-----------------|-------------------|
| **Voice fast ack** | Ollama HTTP (`OLLAMA_BASE_URL` / `OLLAMA_MODEL`) | Does not create mission execution lane by itself. |
| **Mission execution** | Executor → `openclaw agent` → gateway | Missions + receipts + `routing_decided` on the control plane. |

## Receipt metadata (`execution_meta`)

Executor builds:

- **openclaw_model_lane** — same information as legacy **`lane`** (both set for compatibility).
- **lane** — legacy alias for `openclaw_model_lane` (still present).
- **gateway_model** — default agent model string from `openclaw.json` (or `JARVIS_OPENCLAW_GATEWAY_MODEL`).
- **local_model** — tag after `ollama/` when the OpenClaw model lane is `local`.
- **routing** — compact copy of coordinator routing (`requested_lane`, `actual_lane`, `fallback_applied`, `reason_code`, `fallback_reason_code`, etc.).
- **lane_truth** — reconciled block (see table above).
- **mission_execution_path** — `openclaw_executor`.
- **resumed_from_approval** — approval resume path.
- **auth_profiles_present** — when OpenClaw model lane is `gateway`, presence-only hint for cloud auth files.

OpenClaw diagnostics (`attempt_count`, `error_class`, …) are unchanged.

## Mission routing (`routing_decided`)

Posted by the coordinator when DashClaw allows execution. Records **requested** vs **actual** mission path and **fallback** when the classifier preferred `local_fast` but the only mission path is still the gateway executor.

## Operator Value Evals (routing section)

- Counts come from **`routing_decided`** mission events in the UTC window.
- **Requested local_fast** / **Actual gateway path** are explicit row counts (not the same as fallback count alone).
- OpenClaw model lane is **not** duplicated there — inspect execution receipts or mission timeline for `execution_meta`.

## Verification scripts

| Script | Role |
|--------|------|
| `scripts/11-verify-model-lanes.ps1` | Machine readiness: Ollama, OpenClaw CLI, gateway HTTP, `openclaw.json` model, auth file presence. Honest WARN when optional pieces missing. |
| `scripts/11-smoke-model-lanes.ps1` | End-to-end coherence: Ollama direct generate **and** `POST /commands` → `routing_decided` + executor receipt with `execution_meta.lane_truth` / routing. Classifies missing stack honestly. |

`jarvis.ps1` may run `11-verify-model-lanes.ps1 -Startup` (warnings only).

## Voice vs mission execution

- **Voice** may use **direct Ollama** for short replies; that path does **not** write `routing_decided` or executor `execution_meta`.
- **Mission execution** always goes **executor → OpenClaw** when work is run from `jarvis.execution`; the **router** may still record `requested_lane: local_fast` with **fallback** to the gateway mission path.

These are **related but not identical**; the UI uses labels like **OpenClaw model lane** vs **mission route** to keep them separable.

## Configured but not verified

- **Configured**: `openclaw.json` lists a default model string.
- **Not verified**: cloud credentials until you follow OpenClaw docs for `auth-profiles.json`.

For Windows operator setup (env vars, `auth-profiles.json` path, verification commands) without hardcoding provider model slugs in the repo, see [`MINIMAX_SETUP.md`](MINIMAX_SETUP.md).
