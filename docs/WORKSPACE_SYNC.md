# OpenClaw workspace sync

## Three locations (do not confuse them)

1. **`F:\Jarvis` (git repo)**  
   Source code, services, scripts, and **tracked markdown mirrors** under `config/workspace/`.

2. **`config/workspace/*.md` (tracked mirrors)**  
   Reviewable copies of persona/policy files. **Not** the runtime source by themselves until synced. Missing files (`IDENTITY.md`, `USERS.md`) are **expected paths only** until you add them.

3. **`%USERPROFILE%\.openclaw\workspace\main\` (live)**  
   What OpenClaw Gateway uses at runtime. Update by editing mirrors in the repo and running **`scripts/10-sync-openclaw-workspace.ps1`**, or edit live files directly (then consider copying back into the repo for version control).

Mission and control-plane state **never** live in these markdown files; they live in the **Control Plane** API and database.

## Script: `scripts/10-sync-openclaw-workspace.ps1`

- Backs up any existing destination file to  
  `%USERPROFILE%\.openclaw\workspace\main\.jarvis-sync-backups\pre-sync-<timestamp>\`
- Copies only: `SOUL.md`, `AGENTS.md`, `IDENTITY.md`, `USERS.md`, `TOOLS.md` from `config/workspace/`
- Does **not** read or write `auth-profiles.json`, `openclaw.json`, tokens, or secrets
- Prints `[UPDATED]`, `[UNCHANGED]`, `[MISSING-SOURCE]` per file

## MiniMax / cloud auth (manual)

Provider keys and MiniMax profile wiring stay **outside** this sync. After choosing a gateway model (`JARVIS_OPENCLAW_GATEWAY_MODEL` / `openclaw.json`), merge credentials per OpenClaw docs into:

`%USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json`

See also `README.md` and comments in `scripts/03-configure-openclaw.ps1`.
