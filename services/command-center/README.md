# Jarvis Command Center

Governed executive AI command surface for missions and approvals — not a generic admin panel.

## Run

```bash
cd services/command-center
npm install
npm run dev
```

Opens at [http://localhost:5173](http://localhost:5173).

The UI expects the control plane API at [http://localhost:8001](http://localhost:8001) (see `src/lib/api.ts`).

## Navigation

- **Overview** — conversational thread; mission drill-down uses routes, not huge inline dumps.
- **Missions** — list; each row links to **`/missions/:missionId`** (mission detail: timeline, approvals, receipts).
- **Shell focus** — `threadMissionId` in `AppShell` outlet context keeps the **right panel** aligned with the mission the operator is inspecting (thread command, detail page, or future entry points).

## Live updates

- **SSE** to the control plane (`/api/v1/updates/stream`) with **automatic reconnect** (exponential backoff, 30s cap). Shell shows **Live / Reconnecting / Offline** next to the brand on large screens.
- While **not** live, hooks fall back to **periodic REST polling** (same APIs as hydration).
- Mission detail first load uses **`GET /api/v1/missions/:id/bundle`** (mission + events + approvals + receipts) for a single round-trip, then SSE + debounced approval/receipt sync.

## Mission timing (operator)

Mission detail shows compact **Timing** (derived from timeline events + `updated_at`) and a single **Runtime** line (live channel, approvals fetch, execution evidence). See [`docs/MISSION_TIMING.md`](../../docs/MISSION_TIMING.md).

## Voice mode

Voice uses the **same shell focus** as the thread, right panel, and mission detail: `threadMissionId` from `AppShell` (outlet context). It does **not** maintain a separate mission pointer.

**Approval-aware state (visible now)**

- Pending approval on the focused mission: compact **governance brief** (action, risk, reason) plus **View mission**, **Approve**, and **Deny** — same control-plane endpoints as the rest of the Command Center (`POST /api/v1/approvals/:id/decision`).
- Pending approvals on other missions: short line counts only; no second source of truth (data comes from `GET /api/v1/approvals/pending` via live hooks).
- After an approval resolves to **approved**, while the mission is **active**: distinguishes **awaiting execution output** vs **execution updated** using the mission timeline (last `approval_resolved` with `approved` vs receipts after it).
- Orb and title shift to a calm **governance** presentation when the focused mission is in an approval or approval-sync state.

**Intentionally deferred**

- Spoken approve/deny and full voice-side governance workflow are **not** implemented; the mic path remains conversational. Buttons exist for **operator** use only and do not bypass rules.

## Golden path rehearsal

- **Synthetic (control-plane APIs only):** [`docs/GOLDEN_PATH.md`](../../docs/GOLDEN_PATH.md) — [`scripts/13-rehearse-golden-path.ps1`](../../scripts/13-rehearse-golden-path.ps1)
- **Live stack (coordinator, DashClaw, executor, OpenClaw):** [`docs/LIVE_STACK_REHEARSAL.md`](../../docs/LIVE_STACK_REHEARSAL.md) — [`scripts/14-rehearse-live-stack.ps1`](../../scripts/14-rehearse-live-stack.ps1)

Both require `CONTROL_PLANE_API_KEY` when the control plane enforces auth.

## Build

```bash
npm run build
npm run preview
```
