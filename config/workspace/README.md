# OpenClaw workspace mirrors (`config/workspace/`)

This folder holds **tracked markdown** that shapes the **OpenClaw agent’s persona, delegation rules, and tool policy**. Together with `**openclaw.json`** and **auth profiles** (machine-local), it defines *how* the agent behaves when the **executor** runs OpenClaw.

**It does not hold mission state.** Missions, approvals, receipts, and timeline truth live in the **Control Plane** (`services/control-plane/`) and PostgreSQL.

## File-by-file (why each matters)

**Core (in this repo):** `SOUL.md`, `AGENTS.md`, `TOOLS.md`.


| File            | Purpose                                                                                                             |
| --------------- | ------------------------------------------------------------------------------------------------------------------- |
| `**SOUL.md`**   | Core identity and voice: who Jarvis is, mission mindset, operator authority, risk posture.                          |
| `**AGENTS.md`** | Delegation: worker roles, Command Center routing expectations, when to seek approval, channels (voice / web / SMS). |
| `**TOOLS.md**`  | Integrations catalog (e.g. Composio-connected apps) and rules for confirm-before-send / confirm-before-write.       |


**Optional (not required — many setups never add these):**


| File              | Purpose                                                                                                                                                  |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `**IDENTITY.md`** | Only if you want identity split out from `SOUL.md`; **not** in this workspace by default.                                                                |
| `**USERS.md`**    | Only if you want a dedicated user/operator file; **not** in this workspace by default.                                                                   |
| `**MEMORY.md`**   | Optional operator notes in git; **not** copied by the default sync script—see `[docs/OPENCLAW_WORKSPACE_FILES.md](../docs/OPENCLAW_WORKSPACE_FILES.md)`. |


**Full narrative + sync table:** `[docs/OPENCLAW_WORKSPACE_FILES.md](../docs/OPENCLAW_WORKSPACE_FILES.md)`.

## Layers (architecture rule)


| Layer                        | Role                               | Where it lives                                                     |
| ---------------------------- | ---------------------------------- | ------------------------------------------------------------------ |
| **Persona / context**        | How the agent sounds and who it is | `**SOUL.md`** (primary); optional extra files only if you add them |
| **Policy / governance**      | Delegation, tools, guardrails      | `AGENTS.md`, `TOOLS.md`, DashClaw                                  |
| **Mission / operator state** | Source of truth for work           | Control Plane API + DB (not these files)                           |


## What gets synced to the live OpenClaw workspace

`scripts/10-sync-openclaw-workspace.ps1` tries, in order:  
`SOUL.md`, `AGENTS.md`, `IDENTITY.md`, `USERS.md`, `TOOLS.md`  
from this directory → `%USERPROFILE%\.openclaw\workspace\main\`.

- `**IDENTITY.md` / `USERS.md`**: if they are not in `config/workspace/`, the script logs `**[MISSING-SOURCE]`** and continues—that is **normal**; they are optional.
- `**MEMORY.md`** is **optional** and **not** on that list; copy manually to live if you want the gateway to read it.

## Live vs repo

- **Live:** `%USERPROFILE%\.openclaw\workspace\main\` — what the gateway reads at runtime.  
- **Repo:** reviewable mirrors; deploy with `10-sync-openclaw-workspace.ps1`.  
- **Code:** `services/`, `coordinator/`, `executor/`, `voice/`, etc.

```powershell
cd F:\Jarvis
.\scripts\10-sync-openclaw-workspace.ps1
```

