# REPO MAP

## Root
- jarvis.ps1 — master startup script (start here)
- CURRENT_TASK.md — what we are building now
- REPO_MAP.md — this file

## Services
- services/control-plane/ — FastAPI (port 8001), SQLModel, mission state
  - app/main.py — FastAPI app entry
  - app/models/ — Mission, Approval, Receipt, Worker schemas
  - app/api/routes/ — commands, missions, approvals, receipts, sse
- voice/ — Voice server (port 8000)
  - server.py — FastAPI + WebSocket, STT, TTS, Ollama
- executor/ — Executor worker (BEING BUILT)
  - worker.py — reads jarvis.execution, acts, writes jarvis.receipts
- coordinator/ — Event coordinator
  - coordinator.py — Redis Streams consumer, DashClaw routing
- services/command-center/ — React/Vite Command Center (port 5173)
  - src/ — React components

## Config
- .env — environment variables (DO NOT COMMIT)

## OpenClaw workspace
- C:\Users\faizt\.openclaw\workspace\main\ — SOUL.md, AGENTS.md, etc.