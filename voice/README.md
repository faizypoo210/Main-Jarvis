# Jarvis voice server

FastAPI + WebSocket: STT (faster-whisper), optional Ollama acknowledgments, pyttsx3 TTS, Redis stream fan-out.

## Voice approval readout + resolution (v1)

Ephemeral per-WebSocket state in `approval_voice.py` (not persisted to the control plane).

- **List:** e.g. “What needs my approval?” — loads `GET /api/v1/approvals/pending`, speaks a short queue summary, focuses the first approval.
- **Read:** e.g. “Read the next approval” — `GET /api/v1/approvals/{id}/bundle`, prefers `packet.spoken_summary`.
- **Repeat:** “Read that again” — repeats last spoken approval text.
- **Navigate (optional):** “Next approval” / “Previous approval”.
- **Decide:** “Approve it” / “Deny it” only with a focused approval; or `approve <short id>` / `deny <short id>` against the pending list.
- **Refuses:** bare “yes” / “no”, “do it”, “send it”, “merge it”, and bare “approve”/“deny” without the phrases above.

Decisions use `POST /api/v1/approvals/{id}/decision` with `decided_via: "voice"` and `decided_by: "operator"`. Requires `CONTROL_PLANE_API_KEY` for POST.

Other utterances still POST to `POST /api/v1/commands` as before.
