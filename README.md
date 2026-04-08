# JARVIS — AI Command Center

Personal autonomous AI assistant built on OpenClaw, Mission Control,
DashClaw, LobsterBoard, Ollama, and Composio.
Deployed on Windows 11 (10.0.0.249).

## Stack

| Service | Port | Purpose |
|---|---|---|
| Mission Control UI | 3000 | Task orchestration frontend |
| Mission Control API | 3001 | Backend API |
| OpenClaw Gateway | 18789 | AI agent runtime (gpt-5.4) |
| LobsterBoard | 8080 | Operator dashboard |
| Ollama phi4-mini | 11434 | Local GPU fallback model |
| PostgreSQL | 5432 | Mission state database |
| Redis | 6379 | Event bus and cache |
| DashClaw | Vercel | Governance and approvals |

## Machine
- Windows 11, AMD Ryzen 5 3600, RTX 4070 Ti, 32GB RAM
- Local IP: 10.0.0.249
- All services accessible on home WiFi at http://10.0.0.249:<port>

## Repo StructureF:\Jarvis
├── .cursor/rules/          # Cursor AI rules (loaded on every prompt)
├── config/                 # Service configs (secrets redacted)
│   └── workspace/          # OpenClaw agent identity files
│       ├── SOUL.md         # Jarvis personality and operator identity
│       ├── AGENTS.md       # Delegation rules and worker definitions
│       ├── MEMORY.md       # Persistent operator context
│       └── TOOLS.md        # Composio integration capabilities
├── context/                # Architecture docs and full system spec
├── scripts/                # Deployment scripts organized by phase
├── jarvis.ps1              # Master startup — runs the full stack
├── START_HERE.md           # Cursor agent entry point
└── DEPLOYMENT_STATUS.md    # Live phase checklist## Starting JARVIS

```powershell
cd F:\Jarvis
.\jarvis.ps1
```

## Deployment Phases

| Phase | Description | Status |
|---|---|---|
| 1 | Docker + PostgreSQL + Redis | Complete |
| 2 | Mission Control | Complete |
| 3 | OpenClaw Gateway (gpt-5.4) | Complete |
| 4 | LobsterBoard dashboard | Complete |
| 5 | Ollama phi4-mini GPU | Complete |
| 6 | Composio integrations | Complete |
| 7 | Firewall + phone access | Complete |
| 8 | E2E testing | Pending |

## Secrets

All secrets live in Windows User environment variables and
%USERPROFILE%\.openclaw\ — never committed to this repo.

Required environment variables:
- OPENAI_API_KEY — OpenAI API key for gpt-5.4
- COMPOSIO_API_KEY — Composio account API key

Config files with secrets (not in repo):
- %USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json
- C:\projects\openclaw-mission-control\backend\.env
- C:\projects\openclaw-mission-control\.env

## Key Credentials Reference (values in env vars, not here)

| Credential | Location |
|---|---|
| Gateway token | %USERPROFILE%\.openclaw\openclaw.json |
| Mission Control auth token | Windows User env or backend/.env |
| DashClaw API key | Windows User env |
| OpenAI API key | Windows User env: OPENAI_API_KEY |
| Composio API key | Windows User env: COMPOSIO_API_KEY |

## Architecture

See context/ARCHITECTURE.md for full service map and data flow.
See context/JARVIS_SPEC.md for the complete system specification.

## Roadmap

- Phase 8: E2E testing
- Voice stack (wake word, STT, TTS, faster-whisper, Kokoro)
- Event coordinator (Redis Streams glue code)
- Auto-start on Windows boot (Scheduled Task)
- LobsterBoard dashboard layout polish
