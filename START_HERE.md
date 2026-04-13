# Start here (human + agent)

This file is a **pointer**, not an automated deployment runner.

## Before changing behavior

1. Read **`REPO_TRUTH.md`** (ownership and verification).
2. Read **`docs/ARCHITECTURE_V3.md`** or **`context/ARCHITECTURE.md`** for system shape.
3. Follow **`docs/BRINGUP_RUNBOOK.md`** for start order and what “healthy” vs “listening” means today.

## Deploy / verify on a real machine

- Phase checklist: **`DEPLOYMENT_STATUS.md`**
- Bring-up: **`jarvis.ps1`** (prints **bring-up initiated** and per-surface truth — not a blanket “everything online”).
- Stricter readiness: **`scripts/07-verify-jarvis-stack.ps1`** after bring-up (exits non-zero if core gates fail).
- Env names: **`docs/ENV_MATRIX.md`**

## Cursor agents

Project rules live under **`.cursor/rules/`**. Do not treat this file as a script that “executes all phases” without reading the docs above.
