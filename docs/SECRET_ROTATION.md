# Secret rotation checklist

Use this when **any** credential may have been exposed (git history, logs, screenshots, shared scripts) or on a regular cadence. **Do not** store real values in this file.

## How secrets are sourced (canonical)

| Mechanism | Use for |
| --------- | ------- |
| Windows **User** environment variables | Long-lived keys you want outside process-only scope (`[Environment]::GetEnvironmentVariable(..., 'User')` in scripts). |
| Session / Process env | Same shell, CI, or one-off runs (`$env:NAME`). |
| `%USERPROFILE%\.openclaw\openclaw.json` | OpenClaw gateway bind/auth (written by `scripts/03-configure-openclaw.ps1` when `JARVIS_OPENCLAW_GATEWAY_TOKEN` is set). |
| `%USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json` | Provider API keys per OpenClaw (never commit). |
| `services/control-plane/.env` | Control plane DB URL, `SECRET_KEY`, **`CONTROL_PLANE_API_KEY`** (gitignored; copy from `.env.example`). |
| `coordinator/.env`, `executor/.env` | Local process overrides (gitignored); see `.env.example` templates where present. |
| Ephemeral generation | `scripts/02-setup-mission-control.ps1` can generate a random `LOCAL_AUTH_TOKEN` if `JARVIS_MISSION_CONTROL_LOCAL_AUTH_TOKEN` is unset — set the User env to persist across Docker restarts. |

---

## 1. OpenClaw gateway token

| | |
| --- | --- |
| **Purpose** | Authenticates clients to the OpenClaw gateway (WS/HTTP). |
| **Where it lives** | Prefer User env **`JARVIS_OPENCLAW_GATEWAY_TOKEN`**; then `scripts/03-configure-openclaw.ps1` writes it into `%USERPROFILE%\.openclaw\openclaw.json`. |
| **Used by** | OpenClaw CLI, executor (indirectly via OpenClaw), `scripts/03-verify-openclaw.ps1`, Command Center does not embed it (browser uses control plane key). |
| **References** | `README.md`, `docs/SECURITY_REVIEW.md`, `scripts/03-configure-openclaw.ps1`, `scripts/03-verify-openclaw.ps1`, `config/openclaw.json` (template placeholder only). |
| **After rotation** | Set new User env → re-run `03-configure-openclaw.ps1` → restart gateway → verify `03-verify-openclaw.ps1` → update **LobsterBoard** / any widget using `REPLACE_WITH_GATEWAY_TOKEN` in `config/jarvis-dashboard.json`. |

---

## 2. Control plane API key

| | |
| --- | --- |
| **Purpose** | `x-api-key` on control plane HTTP + SSE (`/api/v1/...`, `/api/v1/updates/stream`). |
| **Where it lives** | `services/control-plane/.env` as `CONTROL_PLANE_API_KEY`; clients use User env **`CONTROL_PLANE_API_KEY`** or session env. Smoke/benchmark aliases: `JARVIS_SMOKE_API_KEY`. |
| **Used by** | Command Center (`VITE_CONTROL_PLANE_API_KEY` at build/dev time), coordinator, executor, voice server, all `scripts/*` that call the API. |
| **References** | `services/control-plane/.env.example`, `services/command-center/src/lib/api.ts`, `README.md`. |
| **After rotation** | Update control plane `.env` → restart uvicorn → set same value in User env for scripts → rebuild or set Vite env for Command Center → re-run operator benchmarks if you track baselines. |

---

## 3. DashClaw API key

| | |
| --- | --- |
| **Purpose** | Coordinator calls DashClaw guard / policy (`Authorization: Bearer …`). |
| **Where it lives** | User env **`DASHCLAW_API_KEY`** or `coordinator/.env` (gitignored). |
| **Used by** | `coordinator/coordinator.py`. |
| **References** | `coordinator/README.md`, `docs/E2E_SMOKE_TEST.md`, `scripts/09-smoke-test-e2e.ps1`. |
| **After rotation** | Update coordinator process env → restart coordinator → update `config/jarvis-dashboard.json` if you replaced `REPLACE_WITH_DASHCLAW_KEY` with a real binding locally (file stays placeholder-only in repo). |

---

## 4. PostgreSQL (local dev default)

| | |
| --- | --- |
| **Purpose** | Control plane database. |
| **Where it lives** | `DATABASE_URL` in `services/control-plane/.env`. Docker scripts and `config/database-config.json` use a **documented local dev** password (`jarvis_secure_password_2026` pattern) for the default stack. |
| **Used by** | `scripts/01-install-docker-databases.ps1`, `scripts/02-setup-mission-control.ps1`, control plane SQLAlchemy. |
| **After rotation (recommended for shared or non-dev hosts)** | Change Postgres password in Docker/env → update `DATABASE_URL` everywhere → rotate any derived backups. |

---

## 5. FastAPI `SECRET_KEY` (control plane)

| | |
| --- | --- |
| **Purpose** | Signing/session material for the control plane app (see FastAPI/Starlette usage in project). |
| **Where it lives** | `services/control-plane/.env` (`SECRET_KEY=...`). |
| **After rotation** | Generate a new random string → update `.env` only → restart control plane. |

---

## 6. Legacy Mission Control (optional, deprecated)

| | |
| --- | --- |
| **Purpose** | Bearer for old 3001 API / optional `08-test-mission-control.ps1`. |
| **Where it lives** | User env **`JARVIS_MISSION_CONTROL_TOKEN`**. |
| **Local auth token** | `JARVIS_MISSION_CONTROL_LOCAL_AUTH_TOKEN` for `02-setup-mission-control.ps1` → Mission Control `LOCAL_AUTH_TOKEN` in generated `.env` (never commit). |

---

## 7. Composio / provider keys

| | |
| --- | --- |
| **Purpose** | Third-party tool execution. |
| **Where it lives** | User env **`COMPOSIO_API_KEY`** and OpenClaw `auth-profiles.json`. |
| **References** | `scripts/06-login-composio.ps1`, `scripts/06-verify-composio.ps1`. |

---

## 8. LobsterBoard / dashboard widget tokens

| | |
| --- | --- |
| **Purpose** | HTTP widgets in `config/jarvis-dashboard.json` use **`REPLACE_WITH_*`** placeholders. |
| **After rotation** | Edit your **local** copy or inject at deploy time — do not commit real Bearer tokens. |

---

## 9. `JARVIS_LAN_IP` (not a secret)

| | |
| --- | --- |
| **Purpose** | Convenience only; identifies which IPv4 to print for phone/same-WiFi URLs. |
| **If “leaked”** | No crypto value; rotate only if you care about host fingerprinting in docs (set consistently on the machine). |

---

## Git history caveat

If a real key ever appeared in a tracked file, **rotating the credential** is mandatory; deleting the file is not enough. Use `git log -S` / secret scanning tools on clones as needed.
