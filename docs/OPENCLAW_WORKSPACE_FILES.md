# OpenClaw workspace markdown — what each file does

This document explains how **tracked files under `config/workspace/`** relate to your **live** OpenClaw agent workspace and why they matter for **full product context** on GitHub.

## Two different “truths” (do not merge them)

| Concern | Authoritative location |
|--------|-------------------------|
| **Missions, approvals, receipts, timeline, operator audit** | **Control Plane** API + PostgreSQL (`services/control-plane/`) |
| **Persona, delegation policy, tool rules, voice of the agent** | **OpenClaw workspace markdown** — reviewed in git under `config/workspace/`, **read at runtime** from `%USERPROFILE%\.openclaw\workspace\main\` after sync (or if you edit live) |

The Jarvis stack **depends on both**: the control plane governs *work state*; the workspace files govern *how the agent behaves* when the executor runs OpenClaw. Neither replaces the other.

## Core files (present in `config/workspace/` in this repo)

| File | Role (why it matters) | Synced by `scripts/10-sync-openclaw-workspace.ps1`? |
|------|------------------------|-----------------------------------------------------|
| **`SOUL.md`** | Core **persona**: who Jarvis is, tone, mission framing, operator authority (e.g. Faiz), when to ask vs act. Shapes answers and autonomy style. | **Yes** |
| **`AGENTS.md`** | **Delegation and governance**: worker roles (executor, researcher, coder), Command Center / mission routing expectations, risk rules, **approval channels** (voice, web, SMS). Aligns agent behavior with Jarvis UI and DashClaw. | **Yes** |
| **`TOOLS.md`** | **Tool and integration policy**: what Composio-connected surfaces exist (Gmail, Calendar, Slack, etc.) and **per-action confirmation rules**. Execution still goes through OpenClaw/Composio; this file sets expectations. | **Yes** |

## Optional files (fine if missing — not required)

**`IDENTITY.md`** and **`USERS.md`** are **not** in this workspace and **do not need to be**. Many setups keep identity and operator context in **`SOUL.md`** only. If you later want separate files (e.g. longer identity spec or multi-user notes), add them under `config/workspace/`; until then, ignore **`[MISSING-SOURCE]`** lines for those names in the sync script output.

| File | Role | Synced? |
|------|------|--------|
| **`IDENTITY.md`** | Optional split of persona/identity if you outgrow a single `SOUL.md`. | **Yes**, only **if** the file exists (otherwise skipped). |
| **`USERS.md`** | Optional operator/user mapping or preferences. | **Yes**, only **if** the file exists (otherwise skipped). |
| **`MEMORY.md`** | Optional operator notes; **not** on the script copy list—copy manually to live if desired. | **No** (by design) |

The sync script **iterates** `SOUL.md`, `AGENTS.md`, `IDENTITY.md`, `USERS.md`, `TOOLS.md`. Missing sources log **`[MISSING-SOURCE]`** and **skip**—that is normal for optional files, not a failure.

## Live destination (machine-local)

After sync, the gateway reads:

`%USERPROFILE%\.openclaw\workspace\main\`

Same filenames. **Backups** of previous live files go under  
`.openclaw\workspace\main\.jarvis-sync-backups\pre-sync-<timestamp>\`.

## What is *not* covered by these markdown files

These remain **outside** the workspace sync by design (see `MACHINE_SETUP_STATUS.md`, `docs/WORKSPACE_SYNC.md`):

- **`openclaw.json`** — gateway bind, plugins, default model string  
- **`auth-profiles.json`** — provider credentials  
- **Composio OAuth / API keys** — env and vendor flows  
- **Mission rows** — control plane only  

So “entire OpenClaw project” on disk is **larger** than `config/workspace/`. This repo **represents the governed markdown layer in full**; it **documents and scripts** the rest without storing secrets.

## Workflow for keeping GitHub “complete” for agent behavior

1. Edit persona/policy in **`config/workspace/*.md`** (PR-friendly).  
2. Run **`.\scripts\10-sync-openclaw-workspace.ps1`** on the machine that runs the gateway.  
3. If you edit **live** files only, copy changes **back** into the repo if you want them versioned.

## Editor note

Keep these files **UTF-8** so persona lines render correctly in OpenClaw and on GitHub (avoid mojibake in headings or em dashes).

## Related docs

- [`WORKSPACE_SYNC.md`](./WORKSPACE_SYNC.md) — three locations, script behavior  
- [`../config/workspace/README.md`](../config/workspace/README.md) — short index  
- [`MODEL_LANES.md`](./MODEL_LANES.md) — execution lanes vs control-plane authority  
- [`../REPO_TRUTH.md`](../REPO_TRUTH.md) — ownership boundaries  
