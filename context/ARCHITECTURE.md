# JARVIS Architecture

## Data Flow
Phone/Browser → LobsterBoard (8080)
                    ↓
Voice/Text → OpenClaw Gateway (18789)
                    ↓
            Mission Control (3000/3001)
                    ↓
         PostgreSQL (5432) + Redis (6379)
                    ↓
         Composio → Gmail, Calendar, Slack, Notion, GitHub

## Approval Flow
OpenClaw receives command
    → DashClaw evaluates risk
    → If risky: approval request sent to LobsterBoard
    → Human approves on phone
    → OpenClaw executes

## Local AI (offline fallback)
Ollama (11434) running phi4-mini
OpenClaw routes low-risk tasks to Ollama, complex to Claude

## Container Layout
Host machine runs:
  - jarvis-postgres (Docker)
  - jarvis-redis (Docker)

Docker Compose runs:
  - mission-control-frontend
  - mission-control-backend
  - webhook-worker

Bare processes run:
  - openclaw gateway
  - lobsterboard (node)
  - ollama