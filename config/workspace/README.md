# OpenClaw workspace mirrors (`config/workspace/`)

Tracked **markdown** that shapes the **local OpenClaw** persona, policy, and lightweight context when the executor runs the gateway. **Governed mission truth** (missions, approvals, receipts, routing, Memory v1, Heartbeat v1) lives in the **control plane**, not here.

## Canonical list

Defined in **`governance-manifest.json`** (`required_files` + `sync_order`). Current basenames:

| File | Role |
|------|------|
| `SOUL.md` | Identity, tone, trust stance |
| `IDENTITY.md` | Cross-surface presentation consistency |
| `USERS.md` | Operator authority and approval channels (**not** `USER.md`) |
| `AGENTS.md` | Delegation, routing expectations, worker boundaries |
| `MEMORY.md` | Static context index — **not** Memory v1 DB |
| `HEARTBEAT.md` | Supervision **posture** — **not** Heartbeat v1 engine |
| `TOOLS.md` | Tool policy and receipt expectations |

## Sync and audit

```powershell
.\scripts\11-audit-workspace-governance.ps1
.\scripts\10-sync-openclaw-workspace.ps1
```

**Truth table:** [`docs/OPENCLAW_WORKSPACE_FILES.md`](../docs/OPENCLAW_WORKSPACE_FILES.md)
