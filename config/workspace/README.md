# OpenClaw workspace mirrors (`config/workspace/`)

This folder holds **tracked mirrors** of markdown that shape OpenClaw **persona** and **policy**. It does **not** hold mission state; **missions, approvals, and receipts** are authoritative in the **Control Plane** (`services/control-plane/`) and PostgreSQL.

## Layers (architecture rule)

| Layer | Role | Where it lives |
|-------|------|----------------|
| **Persona / context** | How the agent sounds and who it is | `SOUL.md`, `IDENTITY.md`, `USERS.md` (and related) |
| **Policy / governance** | Delegation, tools, guardrails | `AGENTS.md`, `TOOLS.md`, DashClaw |
| **Mission / operator state** | Source of truth for work | Control Plane API + DB (not these files) |

## Approved sync set

These filenames are the **only** ones copied by `scripts/10-sync-openclaw-workspace.ps1` into `%USERPROFILE%\.openclaw\workspace\main\`:

| File | Status in repo |
|------|------------------|
| `SOUL.md` | Present |
| `AGENTS.md` | Present |
| `TOOLS.md` | Present |
| `IDENTITY.md` | **Expected path:** `config/workspace/IDENTITY.md` (add when ready; not invented here) |
| `USERS.md` | **Expected path:** `config/workspace/USERS.md` (add when ready; not invented here) |

`MEMORY.md` in this folder is optional local notes; it is **not** part of the approved five-file sync. Remove or keep in git per your preference.

## Live vs repo

- **Live OpenClaw workspace:** `%USERPROFILE%\.openclaw\workspace\main\` — what the gateway/agent actually reads.
- **This directory:** versioned snippets to review in PRs and deploy with `10-sync-openclaw-workspace.ps1`.
- **Application code:** `services/`, `coordinator/`, `executor/`, `voice/`, etc.

Run sync after editing tracked files:

```powershell
cd F:\Jarvis
.\scripts\10-sync-openclaw-workspace.ps1
```
