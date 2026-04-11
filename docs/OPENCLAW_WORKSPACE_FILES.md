# OpenClaw workspace markdown — roles, authority, sync

This document is the **file-by-file contract** for tracked mirrors under `config/workspace/`. It complements **`REPO_TRUTH.md`** (ownership) and **`WORKSPACE_SYNC.md`** (locations and workflow).

## Two layers (do not merge)

| Layer | Authoritative for | Location |
|-------|-------------------|----------|
| **Control plane** | Missions, timeline events, approvals, receipts, routing, Memory v1 (`memory_items`), Heartbeat v1 (`heartbeat_findings`), SSE | API + PostgreSQL (`services/control-plane/`) |
| **Workspace markdown** | Persona, tone, delegation expectations, tool policy **intent**, lightweight static context for the **local OpenClaw** runtime | `config/workspace/*.md` → sync → `%USERPROFILE%\.openclaw\workspace\main\` |

Workspace files shape **how the agent presents and reasons**; they **do not** override backend state, enforce approvals by themselves, or replace DashClaw/coordinator policy wiring.

**`MEMORY.md` (here) ≠ Memory v1:** the markdown file is a **human-edited index** for the gateway. **Memory v1** is governed **`memory_items`** data in the control plane (see `docs/` + operator APIs).

**`HEARTBEAT.md` (here) ≠ Heartbeat v1:** the markdown sets **tone and honesty** about supervision. **Heartbeat v1** runs in the control plane (rules, dedupe, `GET /api/v1/operator/heartbeat`).

## Canonical pack (`governance-manifest.json`)

**Single source of list:** `config/workspace/governance-manifest.json` defines `required_files` and `sync_order`.  
`scripts/10-sync-openclaw-workspace.ps1` and `scripts/11-audit-workspace-governance.ps1` use this manifest—**do not** fork file lists without updating it.

### Filename: `USERS.md` (not `USER.md`)

Jarvis and the sync script use **`USERS.md`**. A stray **`USER.md`** in `config/workspace/` triggers audit **WARN**; OpenClaw will not receive it under the canonical name unless renamed.

## Files (what each is / is not)

| File | Purpose | Not for |
|------|---------|--------|
| **`SOUL.md`** | Who Jarvis is: posture, tone, trust stance; mission-oriented habits | Mission rows, approval state, or “final say” over the API |
| **`IDENTITY.md`** | Consistent naming and cross-surface presentation | Permissions or enforcement |
| **`USERS.md`** | Operator authority, approval posture, trusted channels | Replacing control-plane approval records |
| **`AGENTS.md`** | Worker roles, Command Center routing hints, delegation and approval **boundaries** | Defining routes in code; coordinator/executor config |
| **`MEMORY.md`** | Short static context index (URLs, operator name) | Live mission dumps or `memory_items` sync |
| **`HEARTBEAT.md`** | How to speak about supervision: quiet unless actionable | Running checks or storing findings |
| **`TOOLS.md`** | Capability policy map; confirm-before-send/write; receipt **expectations** | Guaranteeing Composio tools are configured on every machine |

## Cursor / Codex skills vs workspace

Project **skills** (e.g. `.cursor` / Codex skill packs) are **editor and agent-harness** contracts. They are **not** automatically the same as OpenClaw workspace files. Only files under `config/workspace/` in the manifest are copied to **`%USERPROFILE%\.openclaw\workspace\main\`** by the Jarvis sync script.

## Live destination and backups

- **Live:** `%USERPROFILE%\.openclaw\workspace\main\` (same basenames as the repo).  
- **Backups:** `.openclaw\workspace\main\.jarvis-sync-backups\pre-sync-<timestamp>\` on each sync overwrite.  
- **Not synced:** `governance-manifest.json`, `README.md` (repo documentation only).

## Out of scope (by design)

- `openclaw.json`, `auth-profiles.json`, OAuth tokens, Composio secrets  
- Mission state  

## Verification

```powershell
cd <repo-root>
.\scripts\11-audit-workspace-governance.ps1
.\scripts\10-sync-openclaw-workspace.ps1
```

## Related

- [`WORKSPACE_SYNC.md`](./WORKSPACE_SYNC.md)  
- [`../config/workspace/README.md`](../config/workspace/README.md)  
- [`../REPO_TRUTH.md`](../REPO_TRUTH.md)  
