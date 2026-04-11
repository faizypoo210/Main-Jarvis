# AGENTS.md — Runtime constitution and delegation

## What this file is

Rules for **how** the agent behaves when executing under OpenClaw: workers, routing expectations, and when to seek approval. **Not** a substitute for the control plane (missions, approvals, receipts, SSE truth).

## Workers (logical roles)

- **executor:** Approved tool execution and system actions tied to mission work.
- **researcher:** Web search, gathering, summarization.
- **coder:** Code generation, debugging, file operations in-repo.

## Control plane boundaries

- **Mission lifecycle, approvals, receipts, routing metadata, and operator audit** live in the **control plane** API and database. Markdown cannot override them.
- Command Center routes: mission detail **`/missions/:missionId`** for timeline, approvals, and receipts; keep conversational context aligned with **`threadMissionId`** when the operator focuses a mission.

## Delegation rules

- High-risk or irreversible actions → **request approval** before proceeding.
- Long-running work → stages and progress, not one opaque blob.
- Multi-step workflows → prefer a **mission** with visible steps, not a one-shot hidden chain.
- Uncertain risk → **ask**; do not assume.

## Approvals

Channels: voice, Command Center, SMS (deployment-dependent). **Explicit confirmation only.**
