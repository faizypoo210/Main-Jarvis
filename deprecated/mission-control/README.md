# Deprecated: openclaw-mission-control (legacy local UI)

This directory holds **legacy, non-primary** artifacts for the old **openclaw-mission-control** stack (ports **3000/3001**). It is **not** part of the current Jarvis product path.

## Active architecture (authoritative)

Use **Command Center** (Vite, typically `:5173`) + **Control Plane** (`:8001`) + **Coordinator** + **Executor** + **Voice**, with **OpenClaw Gateway** and optional **LobsterBoard**. Do not treat Mission Control as authority or as the main operator UI.

## What remains here

| File | Purpose |
|------|---------|
| `mission-control-compose.yml` | Compose template copied into an external clone of `openclaw-mission-control` (separate repo, e.g. under `C:\projects\`) |
| `02-setup-mission-control.ps1` | Clone/configure/build/start that **external** stack (legacy workflows only) |
| `02-verify-mission-control.ps1` | Verify containers and HTTP for that stack |
| `08-test-mission-control.ps1` | Optional Phase 8 API checks against the legacy API (Bearer token) |

## Policy

- **Do not extend** this path for new features; prefer Control Plane + Command Center.
- **Migration:** adopt governed APIs and Command Center; retire dependence on 3000/3001 when possible.
- `jarvis.ps1` **does not** start Mission Control; run scripts here manually only if you still need the old UI.
