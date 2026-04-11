# AGENTS.md — Delegation Rules
## Available Workers
- executor: Handles approved tool execution and system actions
- researcher: Web search, data gathering, summarization
- coder: Code generation, debugging, file operations
## Command Center (web)
- Mission inspection uses **`/missions/:missionId`** for timeline, approvals, and receipts; keep the conversational surface on Overview.
- Shell **`threadMissionId`** aligns the right panel with the mission the operator is focused on (thread, detail route, or list).

## Delegation Rules
- High-risk or irreversible actions → request approval before proceeding
- Long-running tasks → break into stages, report progress
- Multi-step workflows → create a mission, not a one-shot response
- When uncertain about risk level → ask, don't assume
## Approval Channels
Approvals can come from: voice, web UI (Command Center), or SMS.
Wait for explicit confirmation. Do not proceed on implied consent.
