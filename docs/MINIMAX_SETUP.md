# MiniMax / cloud gateway model setup

MiniMax (and other cloud providers) are used as a **gateway model lane through OpenClaw**, not as a hardcoded control-plane model. Mission authority remains with the **control plane**; the executor still runs `**openclaw`** and the gateway; there is no separate “direct MiniMax inside the control plane” path in this repo.

## What selects the cloud model

`**JARVIS_OPENCLAW_GATEWAY_MODEL**` (Windows **User** or **Process** environment variable) is read by `scripts/03-configure-openclaw.ps1` and written into the default agent’s `model` field in:

- `%USERPROFILE%\.openclaw\openclaw.json`
- `%USERPROFILE%\.openclaw\config.json` (same content)

If that variable is unset at configure time, the script defaults to a **local** Ollama-style id (`ollama/qwen3:4b`). Set `JARVIS_OPENCLAW_GATEWAY_MODEL` to whatever **model string your OpenClaw + provider setup expects** for cloud—do **not** hardcode provider-specific slugs in tracked repo files.

## Where provider credentials live

Cloud provider API keys and profiles belong **outside git**, in:

`%USERPROFILE%\.openclaw\agents\main\agent\auth-profiles.json`

Edit that file manually following **OpenClaw** and your **provider** documentation. The exact JSON shape (profile keys, nested fields) depends on those docs and must be filled in by the operator; this repo does not pin a canonical MiniMax profile schema here.

## Gateway token (HTTP auth to the OpenClaw gateway)

The gateway token is **not** stored in repo `.env` files. Set:

`**JARVIS_OPENCLAW_GATEWAY_TOKEN`**

as a Windows **User** environment variable (or ensure it is present in the process environment when you run the configure script). The script fails fast if this is missing.

## PowerShell: set Windows User environment variables

Run in **PowerShell** (adjust values; do not paste real secrets into chat or commit them):

```powershell
# Model id for the OpenClaw default agent (cloud or local—use the string your stack expects)
[Environment]::SetEnvironmentVariable("JARVIS_OPENCLAW_GATEWAY_MODEL", "<your-model-string>", "User")

# Token for OpenClaw gateway HTTP auth (generate/store per your security practice)
[Environment]::SetEnvironmentVariable("JARVIS_OPENCLAW_GATEWAY_TOKEN", "<your-gateway-token>", "User")
```

Open a **new** terminal (or sign out/in) so new User variables are visible to processes that were already running.

## Apply config and verify

From the repo root:

```powershell
.\scripts\03-configure-openclaw.ps1
.\scripts\11-verify-model-lanes.ps1
```

`11-verify-model-lanes.ps1` checks machine readiness (Ollama, OpenClaw CLI, gateway HTTP, `openclaw.json` model). When the configured gateway model is **not** an `ollama/` prefix, it warns if `auth-profiles.json` is missing or empty—it does **not** print secret values.

## Do not do this

- Do **not** commit provider secrets or gateway tokens to git.
- Do **not** put MiniMax API keys (or other cloud provider secrets) in `services/control-plane/.env`, `voice/.env`, or any **tracked** repo env file.
- Do **not** hardcode MiniMax (or other vendor) model slugs in repo code or docs as if they were the only valid value—use `JARVIS_OPENCLAW_GATEWAY_MODEL` and operator-owned config on disk.

## See also

- `[ENV_MATRIX.md](ENV_MATRIX.md)` — machine-wide variables
- `[MODEL_LANES.md](MODEL_LANES.md)` — lane vocabulary and verification scripts
- `[SECRET_ROTATION.md](SECRET_ROTATION.md)` — rotation practices

