# Jarvis voice server

FastAPI + WebSocket: STT (faster-whisper), **subprocess-isolated** TTS, Redis stream fan-out. **Free-form** utterances use the control plane **`POST /api/v1/intake`** (`source_surface: voice`); the spoken reply is the control-plane **reply bundle** (no local LLM “fake ack”).

**Where this fits in the system:** see repo [`docs/ARCHITECTURE_V3.md`](../docs/ARCHITECTURE_V3.md) (voice flow, boundaries vs mission `lane_truth`).

## Run (canonical)

From the **repository root** (the directory that contains the `voice/` package):

```powershell
cd F:\Jarvis
python -m uvicorn voice.server:app --reload --port 8002
```

Use **module** form `voice.server:app` so imports resolve under the `voice` package. Running `uvicorn server:app` only from inside `voice/` is a different layout and is not the supported launch path.

Env: copy `voice/.env.example` to `voice/.env` (or set `REDIS_URL`, `CONTROL_PLANE_URL`, etc.).

**Text-to-speech (Windows stability):** Fresh WAV generation does **not** use a long-lived in-process pyttsx3 engine. The server runs `python -m voice.tts_worker` **per utterance** (stdin = UTF-8 text, stdout = WAV). That isolates flaky Windows SAPI state so one bad synthesis cannot poison the next. The asyncio harness in `tts_isolated.py` applies a timeout (`TTS_SYNTHESIS_TIMEOUT_SEC`, default **45s**, override with `JARVIS_VOICE_TTS_TIMEOUT_SEC`), kills the subprocess on expiry, and logs wall-clock duration. **“Read that again”** still **replays cached base64** from the last successful synthesis — no new subprocess.

**Browser playback:** The static UI (`static/index.html`) resumes `AudioContext` before decoding WAV (required for repeat and other turns after the first). Spoken reply shaping (`spoken_render.py`) keeps **transcript** text full while shortening **TTS input** for long status snapshots.

`server.py` aliases `TTS_WAV_TIMEOUT_SEC` to `TTS_SYNTHESIS_TIMEOUT_SEC` for compatibility with older notes.

## Voice mission briefing + status readout (v1)

Read-only summaries from existing operator GETs (no new mission state). Implemented in `briefing_voice.py`; ephemeral ranked mission list + cursor per WebSocket (not persisted).

**Examples:** “What’s happening?”, “What needs my attention?”, “What am I working on?”, “What’s running?”, “What’s blocked?”, “Read me the top mission”, “Next mission” / “Previous mission”, “What changed recently?”

**Sources (parallel):** `GET /api/v1/missions`, `GET /api/v1/approvals/pending`, `GET /api/v1/operator/heartbeat`, `GET /api/v1/operator/workers`, `GET /api/v1/system/health`, `GET /api/v1/operator/activity`, optional `GET /api/v1/operator/cost-events` (unknown-cost hint only). Mission detail uses `GET /api/v1/missions/{id}/bundle`.

**Order:** WebSocket handler runs **read that again** → **inbox** → **briefing** → **governed action requests** → **approval** → **unified intake** (`POST /api/v1/intake`). If data is missing, the reply says so briefly.

**Precedence:** Briefing only answers **operator snapshot** questions (what is happening, what needs my attention, what’s blocked *as an overview*, next/previous mission, etc.). Utterances that sound like **delegated work** on GitHub, PRs, Gmail, or mailbox/inbox (check, summarize, look through, …) **defer** to unified intake — see `routing_precedence.py`.

## Voice inbox triage (v1)

Actionable **operator inbox** readout + explicit triage only — `inbox_voice.py`. Ephemeral queue + cursor per WebSocket (not persisted). Uses `GET /api/v1/operator/inbox` and, for acknowledge/snooze/dismiss, `POST /api/v1/operator/inbox/{item_key}/acknowledge|snooze|dismiss` with `CONTROL_PLANE_API_KEY`.

**Examples:** “What’s in my inbox?”, “Read me the top inbox item”, “Next inbox item” / “Previous inbox item”, “Acknowledge it”, “Snooze it for one hour” / “Snooze it for four hours”, “Dismiss it”, optional “What kind of item is this?”, “Open the approval” / “Open the mission” (spoken hand-off only — no deep links from voice).

**Safety:** Triage phrases must match **exactly** (after normalization), e.g. “acknowledge it” — not “okay”, “got it”, or “later”. No approval approve/deny here; use the approval voice flow for decisions.

**Repeat:** “Read that again” repeats the last spoken reply, including inbox summaries.

## Voice approval readout + resolution (v1)

Ephemeral per-WebSocket state in `approval_voice.py` (not persisted to the control plane).

- **List:** e.g. “What needs my approval?” — loads `GET /api/v1/approvals/pending`, speaks a short queue summary, focuses the first approval.
- **Read:** e.g. “Read the next approval” — `GET /api/v1/approvals/{id}/bundle`, prefers `packet.spoken_summary`.
- **Repeat:** “Read that again” — repeats the **last** spoken voice reply (inbox, briefing, governed action, approval, or intake reply), handled in `server.py`.
- **Navigate (optional):** “Next approval” / “Previous approval”.
- **Decide:** “Approve it” / “Deny it” only with a focused approval; or `approve <short id>` / `deny <short id>` against the pending list.
- **Refuses:** bare “yes” / “no”, “do it”, “send it”, “merge it”, and bare “approve”/“deny” without the phrases above.

Decisions use `POST /api/v1/approvals/{id}/decision` with `decided_via: "voice"` and `decided_by: "operator"`. Requires `CONTROL_PLANE_API_KEY` for POST.

Other utterances use **`POST /api/v1/intake`** (not `POST /api/v1/commands`). When intake creates a mission, the WebSocket subscribes to that mission id for Redis update TTS as before.

## Voice governed action requests (v1)

Narrow **start phrases** (e.g. “create a GitHub issue”, “open a GitHub draft PR”, “merge GitHub PR”, “draft an email”, “send Gmail draft …”) begin an **ephemeral per-WebSocket draft** — fields are collected stepwise; **say confirm** to `POST` the same `/api/v1/missions/{id}/integrations/github/*` and `/gmail/*` routes the Command Center uses (`requested_via: "voice"`). **Cancel that** / **never mind** abandons the draft.

- **Catalog alignment:** **`GET /api/v1/operator/action-catalog`** (cached per process) supplies field order, spoken prompts, intros, and confirm summaries for the six actions when the control plane returns it; start phrases and validation stay narrow (same integration POST bodies as before).
- **Handoff:** After submit, spoken copy points to **pending approval** and the shared **Approvals** queue (same naming family as Command Center catalog labels).
- **No direct execution:** only creates a **pending approval**; GitHub/Gmail run only after normal approval.
- **Mission:** required — say **last** for the mission from the **previous successful voice intake mission** (tracked per connection), or a full/partial mission UUID.
- **Safety:** vague “send it” / “merge it” are **not** accepted as submit; use **confirm** at the confirmation step. Starting a new action while a draft exists requires **cancel that** first.
- **Operator label:** `requested_by` defaults to `voice_operator`; override with **`JARVIS_VOICE_REQUESTED_BY`** if needed.

## Model lanes (voice vs mission)

Free-form voice no longer generates **local** LLM acknowledgments; operator-facing copy comes from the **control plane intake** response. Mission execution that runs through `jarvis.execution` is still the **OpenClaw executor** path; see repo root `docs/MODEL_LANES.md` for the canonical vocabulary (`requested_lane`, `openclaw_model_lane`, `lane_truth`, etc.).
