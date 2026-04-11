# Operator evaluations and benchmarks

This document describes how to **measure** the current Jarvis operator stack (control plane, mission bundle, approvals, execution evidence, live updates) without changing product architecture. Use it to capture **baselines** before security hardening (for example token rotation) so you can compare runs later using the same harness.

## Artifacts

| Artifact | Purpose |
| -------- | ------- |
| [`scripts/13-rehearse-golden-path.ps1`](../scripts/13-rehearse-golden-path.ps1) | Synthetic **API-only** golden path (fast, minimal deps). See [`GOLDEN_PATH.md`](./GOLDEN_PATH.md). |
| [`scripts/14-rehearse-live-stack.ps1`](../scripts/14-rehearse-live-stack.ps1) | **Live stack** (Redis, coordinator, DashClaw, executor, OpenClaw). See [`LIVE_STACK_REHEARSAL.md`](./LIVE_STACK_REHEARSAL.md). |
| [`scripts/15-benchmark-operator-loop.ps1`](../scripts/15-benchmark-operator-loop.ps1) | Timed benchmark: synthetic path + optional live stack + optional SSE TTFB; writes JSON under `docs/reports/`. |

## Report format (JSON)

Reports are written as `docs/reports/operator-benchmark-<UTC-timestamp>.json` (lightweight, inspectable, no telemetry service).

| Field | Meaning |
| ----- | ------- |
| `schema_version` | `1.0` — bump if fields change. |
| `timestamp_utc` | When the benchmark run finished (UTC ISO-8601). |
| `environment_notes` | `control_plane_url`, `hostname`, `ps_version`, flags, optional `operator_notes` (from `-EnvironmentNotes` or `JARVIS_BENCH_NOTES`). |
| `overall_pass` | `true` only if every rehearsal object has `pass: true`. |
| `rehearsals[]` | One object for **synthetic**; optional second for **live_stack** when `-IncludeLiveStack`. |
| `sse` | Optional: two **curl** `time_starttransfer` measurements (ms) to the SSE stream URL — see limitations below. |
| `notes` | Top-level anomalies (exceptions, missing tools). |

Each rehearsal includes:

- `type`: `synthetic` or `live_stack`
- `pass` / `mission_id` (when known)
- `stages`: per-stage pass/fail where applicable
- `http_roundtrip_ms`: client-measured HTTP times (health, command, approvals, decision, receipt, bundle)
- `event_deltas_ms`: **API truth** — differences between `created_at` on mission events from `GET /api/v1/missions/{id}/events` (same basis as [`MISSION_TIMING.md`](./MISSION_TIMING.md))
- `timings_ms`: derived labels such as bundle consistency (see script comments)
- `wall_clock_total_ms` (live stack only): subprocess duration for `14-rehearse-live-stack.ps1`
- `anomalies`: strings when something was skipped or failed

## What is being measured

### Synthetic rehearsal (always)

- **Control plane health** — Round-trip time for `GET /health` and pass/fail on `status`.
- **Command submission** — `POST /api/v1/commands` round-trip (mission creation latency from the client’s perspective).
- **Time to `approval_requested`** — Delta between `created` and `approval_requested` event timestamps (not the HTTP time of `POST /approvals` alone).
- **Governance window** — Delta between `approval_requested` and `approval_resolved` event timestamps (includes your decision POST and server persistence).
- **Decision POST** — Round-trip for `POST /api/v1/approvals/{id}/decision` (ack latency of the HTTP call; compare to event delta for end-to-end governance).
- **Time to first `receipt_recorded`** — Deltas from `approval_resolved` → first receipt, and `created` → first receipt.
- **Bundle truth** — After a successful synthetic flow, time proxy `receipt_post_to_bundle_verify` = receipt POST RTT + bundle GET RTT (documented in JSON as **not** a single server-side metric).

### Live stack (optional, `-IncludeLiveStack`)

- **Wall clock** — Total time for the full `14` script (dominated by coordinator/executor/OpenClaw; not comparable to synthetic).
- **Event deltas** — After success, same event-based deltas as above for the live mission (API truth for that run).

### SSE / reconnect (optional, default on; use `-SkipSseProbe` to disable)

- **Two sequential HTTP connections** to `GET /api/v1/updates/stream` with **curl** `time_starttransfer` — time to **first byte** of the response.
- Interpretation: a **client-side** proxy for “how fast can I attach to the stream again,” not browser UI latency and **not** a forced server disconnect/reconnect test.

## API truth vs client approximation

| Measurement | Kind |
| ----------- | ---- |
| Event deltas (`created` → `approval_requested`, etc.) | **API truth** — persisted `mission_event.created_at` (same timeline as mission detail). |
| HTTP `*_roundtrip_ms` | **Client approximation** — includes network stack and client; comparable across runs on the same machine. |
| `time_to_bundle_truth_consistency_ms` (synthetic) | **Approximation** — sum of two RTTs; use for rough regression only. |
| Live stack `wall_clock_total_ms` | **Wall clock** — includes polling intervals and external runtimes; compare trend, not absolute SLA. |
| SSE TTFB | **curl / HTTP** — not the Command Center React client; omit with `-SkipSseProbe` if curl is unavailable. |

## What “good enough” looks like

Exact numbers depend on hardware and network. Treat these as **qualitative** guardrails:

- **Synthetic** `pass: true` on a warm control plane: HTTP health and command submission are usually **small** (tens to low hundreds of ms on localhost); event deltas for the synthetic path should be **finite** and ordered (created → approval_requested → approval_resolved → receipt_recorded).
- **Governance window** (`approval_requested` → `approval_resolved`) includes human or script decision time — compare **before/after** policy changes, not against a universal millisecond budget.
- **Live stack** first run after cold start can take **minutes** for executor receipt; failure is informative (`LIVE_STACK_FAIL stage=…`).
- **SSE** first-byte times should be **repeatable** on localhost; large swings suggest load, firewall, or stream blocking — not “optimistic” stability.

## Baseline capture workflow (pre–security hardening)

Run in this order on the machine and stack you care about:

1. **Synthetic golden path** — `.\scripts\13-rehearse-golden-path.ps1`  
   Confirms APIs and auth before you spend time on the full stack.

2. **Live-stack rehearsal** — `.\scripts\14-rehearse-live-stack.ps1`  
   Confirms Redis → coordinator → DashClaw → executor → receipts end-to-end.

3. **Benchmark operator loop** —  
   ```powershell
   $env:CONTROL_PLANE_API_KEY = '<key>'
   .\scripts\15-benchmark-operator-loop.ps1 -EnvironmentNotes "pre-rotation baseline; branch=…"
   # Optional full stack timing + event deltas for the live mission:
   # .\scripts\15-benchmark-operator-loop.ps1 -IncludeLiveStack -EnvironmentNotes "…"
   ```

Store the JSON files (or attach them to the release ticket). After token rotation or security tightening, repeat with the **same** flags and similar machine load; diff JSON fields rather than relying on memory.

## Comparing runs after security hardening

- Keep **`environment_notes.operator_notes`** and **`control_plane_url`** comparable.
- Prefer **event deltas** and **stage pass/fail** over raw HTTP RTT when diagnosing governance or execution.
- Expect **HTTP** times to change slightly with TLS, reverse proxies, or auth — compare **order of magnitude** and **failures**, not sub-millisecond wins.
- **Do not** treat SSE curl TTFB as a substitute for real operator UX; it is a narrow transport probe.

## What still cannot be measured cleanly without more surface area

- **Command Center UI paint time** and **voice overlay** latency — not in this harness (no browser automation).
- **True SSE reconnect after server idle or TCP drop** — not injected here; only sequential client connects.
- **Per-stage live-stack time** inside `14` — wall clock is one number; granular breakdown would require instrumenting that script or new server spans (out of scope for “no architecture change”).
- **Operator cognitive / decision time** — included inside governance event deltas; cannot be separated without explicit UI timestamps.

## Safety

Benchmark scripts use the same **non-destructive** patterns as rehearsals: normal missions, approvals, and receipts — no identity scraping, no data wiping. Do not point at production unless you intend to create real mission rows there.
