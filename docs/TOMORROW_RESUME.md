# Tomorrow resume pack

**Use this** after a break: quick orientation without re-reading the whole repo.

---

## 1. What is implemented (ground truth)

- **Governed control plane** (PostgreSQL): missions, events, approvals, receipts, operator APIs (inbox, heartbeat, workers, cost, memory, evals), governed GitHub/Gmail workflows (approval-gated, narrow scope).
- **Command Center**: missions, approvals (review bundles), inbox, activity, workers, cost, integrations readiness, governed action launchers from catalog.
- **Voice**: inbox triage, briefing, governed action **requests**, approval readout/decisions, `POST /commands` — all via control plane APIs.
- **SMS** (optional Twilio): outbound codes + inbound decisions; reminders/escalation when heartbeat + env enabled.
- **Day-wrap reporting**: `scripts/19-day-wrap-snapshot.ps1` → `docs/reports/day-wrap-*.md`.

**Architecture:** [`ARCHITECTURE_V3.md`](ARCHITECTURE_V3.md).

---

## 2. What landed recently

Run locally (updates every session):

```powershell
cd F:\Jarvis
git log -10 --oneline
```

---

## 3. Still manual / environment-dependent

- `%USERPROFILE%\.openclaw\` — gateway, auth profiles, live workspace (sync from `config/workspace/` when needed).
- **Secrets**: `CONTROL_PLANE_API_KEY`, GitHub/Gmail/Twilio tokens — User env or `.env` files (gitignored).
- **Heartbeat worker**: not started by `jarvis.ps1`; start manually if you need scheduled supervision/reminders.
- **Public SMS webhook**: tunnel or hosted URL for Twilio to hit your control plane.

Full matrix: [`ENV_MATRIX.md`](ENV_MATRIX.md).

---

## 4. Suggested next pass (pick one)

- **Ops:** Run `.\scripts\19-day-wrap-snapshot.ps1` after bring-up; fix any FAIL rows.
- **Execution:** With gateway + coordinator + executor up, run `.\scripts\09-smoke-test-e2e.ps1`.
- **Product:** Continue from `STATUS.md` ledger — avoid duplicating architecture work already in V3 docs.

---

## 5. Quick commands — working dev state

```powershell
cd F:\Jarvis

# Start core stack (Windows)
.\jarvis.ps1

# Optional: heartbeat worker (separate terminal)
# $env:CONTROL_PLANE_API_KEY = "<same as control plane>"
# python heartbeat\heartbeat.py

# Sanity
Invoke-WebRequest http://localhost:8001/health -UseBasicParsing
.\scripts\08-smoke-operator-control-plane.ps1

# Broader check (needs full infra)
# .\scripts\08-final-report.ps1
# .\scripts\19-day-wrap-snapshot.ps1
```

**Bring-up detail:** [`BRINGUP_RUNBOOK.md`](BRINGUP_RUNBOOK.md). **Machine checklist:** [`MACHINE_SETUP_STATUS.md`](../MACHINE_SETUP_STATUS.md).
