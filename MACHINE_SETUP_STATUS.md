# Machine setup status (cannot be guaranteed by git alone)

Use this as a **checklist** for what must exist on the **host** for Jarvis to run as documented. This repo does not contain secrets or your OpenClaw home directory.

## Environment variables (representative)

Check **`services/control-plane/.env.example`**, **`executor/.env.example`**, **`coordinator/.env.example`**, **`voice/`** (`.env` beside `server.py` if used), and **root README** for names. Common ones:

| Variable | Used for |
|----------|-----------|
| `DATABASE_URL` | Control plane → PostgreSQL |
| `REDIS_URL` | Control plane realtime, coordinator, executor, voice |
| `SECRET_KEY` | Control plane |
| `CONTROL_PLANE_API_KEY` | Mutating API auth (must match client/scripts) |
| `ALLOWED_ORIGINS` | CORS for Command Center / LAN |
| `CONTROL_PLANE_URL` | Coordinator, executor, voice → API base |
| `DASHCLAW_BASE_URL`, `DASHCLAW_API_KEY` | Coordinator governance calls |
| `OLLAMA_MODEL`, `OLLAMA_BASE_URL` / `OLLAMA_HOST` | Voice + local lane |
| `JARVIS_OPENCLAW_GATEWAY_MODEL` | Optional override for gateway default model (see README) |
| `JARVIS_LAN_IP` | Advertised LAN URL for scripts / phone access |
| `COMPOSIO_API_KEY` | Composio (if used) |
| `WHISPER_DEVICE` | Voice STT (CPU vs CUDA) |

**Rule:** Set secrets in **User** environment on Windows or a secure secret store—**never commit** `.env` with real values.

## Provider auth

- **OpenClaw**: `%USERPROFILE%\.openclaw\openclaw.json`, `auth-profiles.json`, gateway token as per **`docs/SECRET_ROTATION.md`**.
- **Composio / cloud LLM**: per vendor; not in repo.

## OpenClaw auth profiles

- Path (typical): `%USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json`
- **MACHINE_CONFIG_REQUIRED:** cloud execution fails without valid profiles.

## Local services (typical)

- [ ] Docker Desktop running (if using containerized Postgres/Redis)
- [ ] `jarvis-postgres` and `jarvis-redis` up (or equivalent endpoints)
- [ ] PostgreSQL reachable at `DATABASE_URL`
- [ ] Redis reachable at `REDIS_URL`
- [ ] OpenClaw gateway running if testing executor **or** live-stack rehearsal
- [ ] Ollama running if using local lane / voice defaults

## Scripts / scheduled tasks

- [ ] `jarvis.ps1` or per-service starts as you prefer
- [ ] Optional: Windows Scheduled Task for auto-start (not in-repo; mentioned in README roadmap)

## Tunnels / remote access

- Firewall rules: **`scripts/07-firewall-rules.ps1`** (admin) per deployment docs
- **No** tunnel config is authoritative in this repo—bring your own if exposing beyond LAN

## Machine-specific prerequisites

- [ ] Python venvs for control plane, coordinator, executor, voice (see each folder’s README)
- [ ] Node.js for Command Center (`npm install` / `npm run dev`)
- [ ] `openclaw` on PATH (Windows `openclaw.cmd` path used by executor default)
- [ ] GPU drivers if using CUDA whisper path (`WHISPER_DEVICE=cuda`)

## Sync OpenClaw workspace mirrors

After editing `config/workspace/*.md`, run the audit then sync (canonical list: **`governance-manifest.json`**):

```powershell
cd F:\Jarvis
.\scripts\11-audit-workspace-governance.ps1
.\scripts\10-sync-openclaw-workspace.ps1
```

Live files remain under `%USERPROFILE%\.openclaw\workspace\main\`. See **`docs/OPENCLAW_WORKSPACE_FILES.md`**.

## Quick “am I aligned?” checks

1. Control plane: `curl http://localhost:8001/health` (or Invoke-WebRequest)
2. Command Center: open `http://localhost:5173` after `npm run dev`
3. Golden path (API truth): `scripts/13-rehearse-golden-path.ps1` with `CONTROL_PLANE_API_KEY` if required

See **`REPO_TRUTH.md`** → Verification sources for more.
