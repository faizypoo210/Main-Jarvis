# AGENTS.md — Delegation Rules

> **Codebase:** All Jarvis application source lives in **`F:\Jarvis`**. See **`docs/AGENT_CONTEXT.md`** for the full module map. Authoritative OpenClaw policy files live in **`%USERPROFILE%\.openclaw\workspace\main\`** (this `config/workspace/` path may hold a short mirror only).

## Available Workers
- executor: Handles approved tool execution and system actions
- researcher: Web search, data gathering, summarization
- coder: Code generation, debugging, file operations
## Delegation Rules
- High-risk or irreversible actions → request approval before proceeding
- Long-running tasks → break into stages, report progress
- Multi-step workflows → create a mission, not a one-shot response
- When uncertain about risk level → ask, don't assume
## Approval Channels
Approvals can come from: voice, web UI (Mission Control), or SMS.
Wait for explicit confirmation. Do not proceed on implied consent.
