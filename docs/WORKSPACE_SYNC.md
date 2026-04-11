# OpenClaw workspace sync

**File roles and authority split:** **[`OPENCLAW_WORKSPACE_FILES.md`](./OPENCLAW_WORKSPACE_FILES.md)** (canonical).

## Three locations (do not confuse them)

1. **Git repo (`config/workspace/`)** — Reviewable mirrors; list driven by **`governance-manifest.json`**.
2. **Live OpenClaw workspace** — `%USERPROFILE%\.openclaw\workspace\main\` — what the gateway reads at runtime.
3. **Control plane** — Mission/approval/receipt/routing truth in PostgreSQL (not these markdown files).

## Scripts

| Script | Purpose |
|--------|---------|
| **`scripts/10-sync-openclaw-workspace.ps1`** | Repo → live copy for every file in `sync_order`; **fails** if a `required_files` entry is missing from disk; warns on `USER.md` drift |
| **`scripts/11-audit-workspace-governance.ps1`** | PASS/WARN/FAIL audit: required files, manifest vs sync script, docs consistency |

Backups of overwritten live files: `%USERPROFILE%\.openclaw\workspace\main\.jarvis-sync-backups\pre-sync-<timestamp>\`

**Not copied:** `governance-manifest.json`, this folder’s `README.md` (repo-only).

## MiniMax / cloud auth (manual)

Provider keys stay outside sync. See `README.md` and `scripts/03-configure-openclaw.ps1`.
