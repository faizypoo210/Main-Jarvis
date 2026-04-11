# Jarvis voice server

FastAPI + WebSocket: STT (faster-whisper), optional Ollama acknowledgments, pyttsx3 TTS, Redis stream fan-out.

## Voice mission briefing + status readout (v1)

Read-only summaries from existing operator GETs (no new mission state). Implemented in `briefing_voice.py`; ephemeral ranked mission list + cursor per WebSocket (not persisted).

**Examples:** “What’s happening?”, “What needs my attention?”, “What am I working on?”, “What’s running?”, “What’s blocked?”, “Read me the top mission”, “Next mission” / “Previous mission”, “What changed recently?”

**Sources (parallel):** `GET /api/v1/missions`, `GET /api/v1/approvals/pending`, `GET /api/v1/operator/heartbeat`, `GET /api/v1/operator/workers`, `GET /api/v1/system/health`, `GET /api/v1/operator/activity`, optional `GET /api/v1/operator/cost-events` (unknown-cost hint only). Mission detail uses `GET /api/v1/missions/{id}/bundle`.

**Order:** WebSocket handler runs **read that again** → **briefing** → **approval** → **POST /commands** → Ollama ack. If data is missing, the reply says so briefly.

## Voice approval readout + resolution (v1)

Ephemeral per-WebSocket state in `approval_voice.py` (not persisted to the control plane).

- **List:** e.g. “What needs my approval?” — loads `GET /api/v1/approvals/pending`, speaks a short queue summary, focuses the first approval.
- **Read:** e.g. “Read the next approval” — `GET /api/v1/approvals/{id}/bundle`, prefers `packet.spoken_summary`.
- **Repeat:** “Read that again” — repeats the **last** spoken voice reply (briefing, approval, or Ollama ack), handled in `server.py`.
- **Navigate (optional):** “Next approval” / “Previous approval”.
- **Decide:** “Approve it” / “Deny it” only with a focused approval; or `approve <short id>` / `deny <short id>` against the pending list.
- **Refuses:** bare “yes” / “no”, “do it”, “send it”, “merge it”, and bare “approve”/“deny” without the phrases above.

Decisions use `POST /api/v1/approvals/{id}/decision` with `decided_via: "voice"` and `decided_by: "operator"`. Requires `CONTROL_PLANE_API_KEY` for POST.

Other utterances still POST to `POST /api/v1/commands` as before.

## Model lanes (voice vs mission)

Fast Ollama acknowledgments in this service use **direct HTTP** to Ollama when configured. That path does **not** populate mission `routing_decided` or executor `execution_meta`. Mission work that runs through `jarvis.execution` is always the **OpenClaw executor** path; see repo root `docs/MODEL_LANES.md` for the canonical vocabulary (`requested_lane`, `openclaw_model_lane`, `lane_truth`, etc.).
