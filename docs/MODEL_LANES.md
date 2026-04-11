# Model lanes (local vs cloud execution)

> **Truth boundary:** model lane choice does **not** move mission authority off the control plane. For ownership and machine config, see [`../REPO_TRUTH.md`](../REPO_TRUTH.md) and [`../MACHINE_SETUP_STATUS.md`](../MACHINE_SETUP_STATUS.md).

This document describes how **two model lanes** are used in JARVIS without changing control-plane authority.

## Roles

| Lane | Intent | Typical path |
|------|--------|----------------|
| **Local fast** | Low-latency, on-box inference | **Ollama** with `OLLAMA_MODEL` (default `qwen3:4b`) |
| **Cloud execution** | Agent/tools via OpenClaw | **OpenClaw CLI** → gateway → model configured in `openclaw.json` (e.g. MiniMax via provider profiles) |

**Control Plane** remains the source of truth for missions, receipts, and events. Model lanes affect **how work is executed**, not where authority lives.

## What uses Ollama locally

- **Voice server** (`voice/server.py`): acknowledgment / short replies use `OLLAMA_BASE_URL` + `OLLAMA_MODEL` (default `qwen3:4b`).
- **Optional**: OpenClaw gateway model may be set to `ollama/qwen3:4b` so the **executor** still goes through OpenClaw but targets local Ollama (same weights, different routing). In that case executor receipts show `execution_meta.lane` = `local`.

## What uses OpenClaw / cloud

- **Executor** (`executor/executor.py`): every `jarvis.execution` message is handled with `openclaw agent` (gateway). The **configured default agent model** in `%USERPROFILE%\.openclaw\openclaw.json` determines whether traffic goes to **Ollama via OpenClaw** (`ollama/...`) or a **cloud provider** (non-`ollama/` model id).
- **MiniMax 2.5** (or any cloud model) is selected only via **your** gateway model string and **your** `auth-profiles.json` entries — **no provider slug is hardcoded** in this repo.

## Receipt metadata (`execution_meta`)

Executor receipts include a safe, structured block (no secrets, no tokens):

- `lane`: `local` if gateway model string starts with `ollama/`, else `gateway` (cloud/other).
- `gateway_model`: default agent model string from `openclaw.json` (or `JARVIS_OPENCLAW_GATEWAY_MODEL` if JSON has no default).
- `local_model`: tag after `ollama/` when `lane` is `local`; otherwise omitted/null.
- `resumed_from_approval`: `true` when execution payload carried `resumed` or `approval_id` (approval resume path).
- `auth_profiles_present` (only when `lane` is `gateway`): `true` if `auth-profiles.json` exists and parses to a non-empty object (presence only).

OpenClaw failures also record **diagnostic fields** on the same receipt payload (truncated/sanitized stderr, no tokens): `attempt_count` (max two tries with backoff on transient cases), `error_class` (stable string such as `timeout`, `empty_output`, `auth_or_config_error`), `exit_code` when the subprocess exited, `stderr_excerpt`, and `final_success` (mirrors `success`).

Mission timeline events (`receipt_recorded`) mirror `execution_meta` for UI and smoke tests.

## Configured but not verified

- **Configured**: `openclaw.json` lists a default model string.
- **Not verified**: cloud credentials may be missing or invalid until you edit `auth-profiles.json` and env per OpenClaw docs. Symptoms: empty agent output, CLI errors, or gateway warnings — check `openclaw status` and gateway logs.

## Manual steps in `%USERPROFILE%\.openclaw\`

1. **`openclaw.json` / `config.json`**  
   Set the default agent `model` to your provider id (or `ollama/qwen3:4b` for local-via-OpenClaw). Prefer User env `JARVIS_OPENCLAW_GATEWAY_MODEL` when running `scripts/03-configure-openclaw.ps1` so the slug is not guessed in-repo.

2. **`agents\main\agent\auth-profiles.json`**  
   Add provider credentials **exactly as OpenClaw documents** for MiniMax or other clouds. This repo does not invent schema or env names.

3. **Gateway token**  
   Remains in `openclaw.json` or `JARVIS_OPENCLAW_GATEWAY_TOKEN` as already documented.

## Verification scripts

- `scripts/11-verify-model-lanes.ps1` — Ollama, `qwen3:4b` (or `OLLAMA_MODEL`), OpenClaw CLI, gateway HTTP, `openclaw.json` model, auth file presence (no secret dump).
- `scripts/11-smoke-model-lanes.ps1` — Ollama `/api/generate` plus one safe command through control plane → executor → receipt with `execution_meta`.

`jarvis.ps1` runs `11-verify-model-lanes.ps1 -Startup` after the gateway starts (warnings only).

## Mission routing authority (control plane + coordinator)

Mission commands (Command Center → Redis → coordinator → DashClaw → `jarvis.execution`) carry an explicit **routing decision** separate from OpenClaw’s **gateway model** string:

- **`routing_decided`** mission events record the **requested** lane (`local_fast` vs `gateway`) from deterministic v1 heuristics, the **actual** lane used for the mission executor path, and **fallback** when the classifier preferred `local_fast` but execution still goes through the OpenClaw executor (the only mission execution path today).
- **Executor receipts** (`execution_meta.routing`) include the same compact fields (no secrets).

This is **routing authority + observability**: it does not add a second mission executor runtime. Voice and other surfaces may still use direct Ollama for fast acks; that path is separate from mission execution.

## Voice vs executor

- **Voice** talks to Ollama **directly** for fast acks.
- **Executor** talks to OpenClaw only. To force all text through one stack, you would change product behavior; today the architecture keeps voice local-fast and mission execution on the gateway path by design.
