# Operator evaluations and benchmarks

This document describes how to **measure** the current Jarvis operator stack (control plane, mission bundle, approvals, execution evidence, live updates) without changing product architecture. Use it to capture **baselines** before security hardening (for example token rotation) so you can compare runs later using the same harness.

## Artifacts

| Artifact | Purpose |
| -------- | ------- |
| [`scripts/13-rehearse-golden-path.ps1`](../scripts/13-rehearse-golden-path.ps1) | Synthetic **API-only** golden path (fast, minimal deps). See [`GOLDEN_PATH.md`](./GOLDEN_PATH.md). |
| [`scripts/14-rehearse-live-stack.ps1`](../scripts/14-rehearse-live-stack.ps1) | **Live stack** (Redis, coordinator, DashClaw, executor, OpenClaw). See [`LIVE_STACK_REHEARSAL.md`](./LIVE_STACK_REHEARSAL.md). |
| [`scripts/15-benchmark-operator-loop.ps1`](../scripts/15-benchmark-operator-loop.ps1) | Timed benchmark: synthetic path + optional live stack + optional SSE TTFB; writes JSON under `docs/reports/`. |
| [`scripts/16-verify-harness-semantics.ps1`](../scripts/16-verify-harness-semantics.ps1) | **Regression-only:** validates synthetic isolation markers in `13`, fixture-based parsing of `14` output, and benchmark summary logic — **no stack required** (seconds). |
| [`scripts/17-verify-operator-evals.ps1`](../scripts/17-verify-operator-evals.ps1) | **Orchestrator:** runs `16` → `13` → optional `15` (synthetic-only); prints **`classification_source`** (`semantics` \| `synthetic` \| `benchmark` \| `none`) plus **`overall_classification`**. **Not** auto-started; explicit operator command. |

## Recommended quick check (eval / harness layer)

| Goal | Command |
| ---- | ------- |
| **Fastest** (no control plane, no missions) | `.\scripts\16-verify-harness-semantics.ps1` |
| **Normal operator confidence** (semantics + golden path, no benchmark JSON) | `.\scripts\17-verify-operator-evals.ps1 -SkipBenchmark` |
| **Full harness check + artifact** (adds synthetic-only benchmark report under `docs/reports/`) | `.\scripts\17-verify-operator-evals.ps1` |

Requires `CONTROL_PLANE_API_KEY` (and control plane up) for steps after `16`. Use `-SkipRedisIsolationVerify` on `17` or `13` if Redis XLEN is unavailable. Use `-BenchmarkOutputDir` for `15` JSON output location. Use `-BenchmarkSkipSseProbe` on `17` to skip curl SSE timing in the benchmark step.

### Outcome classification (`17` and `13`)

`17` prints **`overall_classification`** and **`classification_source`** (which step drove the result: `semantics`, `synthetic`, `benchmark`, or `none` when all required steps pass) so a failed run is not a single undifferentiated failure:

| Classification | Meaning |
| ---------------- | ------- |
| **pass** | Required steps succeeded. |
| **harness_fail** | `16` failed — the eval harness (parsing / isolation markers / benchmark summary logic) likely **regressed** in-repo; fix scripts or fixtures first. |
| **precondition_fail** | The stack or environment was **not ready** for the rehearsal (e.g. control plane down, wrong API key, Redis isolation noise, 5xx, connection errors). `13` also prints **`GOLDEN_PATH_SYNTHETIC_CLASS=precondition_fail`**. |
| **contract_drift** | The rehearsal script and the **live control-plane API** no longer agree (e.g. HTTP **422** validation on `POST /api/v1/approvals`, or bundle/event assertions failing after successful HTTP). `13` prints **`GOLDEN_PATH_SYNTHETIC_CLASS=contract_drift`** and, for 422, echoes response body hints and points at `services/control-plane/app/schemas/approvals.py`. |

`13` sends an **`ApprovalCreate`-shaped** body including **`command_text`** (same as the mission command) so it matches coordinator-style requests. On validation errors it surfaces **HTTP status and response body** instead of only the generic exception message.

### Synthetic approval payload contract (`13` / `15`)

`13-rehearse-golden-path.ps1` and `15-benchmark-operator-loop.ps1` **share one operator-side contract** for `POST /api/v1/approvals`: [`scripts/lib/ApprovalPayloadContract.ps1`](../scripts/lib/ApprovalPayloadContract.ps1). Both call `New-SyntheticApprovalCreatePayload` and `Test-ApprovalCreatePayload` before the HTTP request so obvious mistakes are caught as **contract drift** (with a clear message) instead of an unexplained **422**.

The control plane defines **`requested_via`** and **`decided_via`** as the literal set `voice | command_center | system | sms` in [`services/control-plane/app/schemas/approvals.py`](../services/control-plane/app/schemas/approvals.py) (`ApprovalSurface`). Synthetic scripts use **`command_center`** (Command Center-shaped); the coordinator uses **`system`** when it posts approvals from the runtime pipeline.

**HTTP 422** on approval creation is treated in operator tooling as **likely contract drift** (script body vs `ApprovalCreate`), not as a generic “stack is down” failure — compare the local contract file with the schema and fix the script or the server model in tandem.

## Report format (JSON)

Reports are written as `docs/reports/operator-benchmark-<UTC-timestamp>.json` (lightweight, inspectable, no telemetry service).

| Field | Meaning |
| ----- | ------- |
| `schema_version` | `1.1` — includes harness vs hard-failure semantics (see below). |
| `timestamp_utc` | When the benchmark run finished (UTC ISO-8601). |
| `environment_notes` | `control_plane_url`, `hostname`, `ps_version`, flags, optional `operator_notes` (from `-EnvironmentNotes` or `JARVIS_BENCH_NOTES`). |
| `overall_pass` | `true` when **no rehearsal has `hard_failure: true`** (runtime not broken). Known policy/harness outcomes do **not** force this to `false`. |
| `overall_strict_pass` | `true` only when **every** rehearsal has `outcome_class: "pass"` (ideal path: synthetic bundle OK **and** live stack full approval-gated path, if `-IncludeLiveStack`). |
| `summary_has_known_harness_findings` | `true` if any rehearsal has `outcome_class: "known_nonblocking"` (e.g. DashClaw allowed execution before approval). |
| `rehearsals[]` | One object for **synthetic**; optional second for **live_stack** when `-IncludeLiveStack`. |
| `sse` | Optional: two **curl** `time_starttransfer` measurements (ms) to the SSE stream URL — see limitations below. |
| `notes` | Top-level anomalies (exceptions, missing tools). |

**Compatibility:** In `1.0`, `overall_pass` meant every rehearsal had `pass: true`. In `1.1`, prefer `overall_pass` + `hard_failure` + `outcome_class` — `pass` on a rehearsal may still be `true` for a healthy live stack when `outcome_class` is `known_nonblocking`.

Each rehearsal includes:

- `type`: `synthetic` or `live_stack`
- `pass` — still present; for live stack, `true` for both ideal pass and `known_nonblocking` (no hard failure)
- `hard_failure` — `true` only for genuine harness/API/runtime failures
- `outcome_class`: `pass` | `known_nonblocking` | `hard_fail`
- `classification` — e.g. `policy_allowed_execution` when live stack prints `LIVE_STACK_RESULT` with `status=known_nonblocking`
- `known_findings` — short strings (e.g. policy allowed execution before approval gate)
- `mission_id` (when known)
- `stages`: per-stage pass/fail where applicable
- `http_roundtrip_ms`: client-measured HTTP times (health, command, approvals, decision, receipt, bundle)
- `event_deltas_ms`: **API truth** — differences between `created_at` on mission events from `GET /api/v1/missions/{id}/events` (same basis as [`MISSION_TIMING.md`](./MISSION_TIMING.md))
- `timings_ms`: derived labels such as bundle consistency (see script comments)
- `wall_clock_total_ms` (live stack only): subprocess duration for `14-rehearse-live-stack.ps1`
- `anomalies`: strings when something was skipped or failed

**Synthetic isolation:** The benchmark’s synthetic path sends `context.rehearsal_mode` / `context.skip_runtime_publish` (same as `13`) so it does not publish to Redis and will not collide with a running coordinator/executor.

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
- **Live stack** first run after cold start can take **minutes** for executor receipt; genuine problems are informative (`LIVE_STACK_FAIL stage=…`). A **`known_nonblocking`** / `policy_allowed_execution` outcome (receipt before approval) is **healthy** for benchmark `overall_pass` but yields `overall_strict_pass: false` until you use command text that forces `requires_approval`.
- **SSE** first-byte times should be **repeatable** on localhost; large swings suggest load, firewall, or stream blocking — not “optimistic” stability.

## Baseline capture workflow (pre–security hardening)

Run in this order on the machine and stack you care about:

0. **Harness semantics (optional, fast)** — `.\scripts\16-verify-harness-semantics.ps1`  
   Confirms isolation markers and benchmark parse/summary logic without starting services.

1. **Single entrypoint (optional)** — `.\scripts\17-verify-operator-evals.ps1` (see **Recommended quick check** above)  
   runs `16` → `13` → optional `15` in one pass.

2. **Synthetic golden path** — `.\scripts\13-rehearse-golden-path.ps1`  
   Confirms APIs and auth before you spend time on the full stack.

3. **Live-stack rehearsal** — `.\scripts\14-rehearse-live-stack.ps1`  
   Confirms Redis → coordinator → DashClaw → executor → receipts end-to-end.

4. **Benchmark operator loop** —  
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

## Regression semantics (harness)

Run `.\scripts\16-verify-harness-semantics.ps1` after changes to rehearsals or `scripts/lib/Parse-LiveStackHarnessOutput.ps1` so benchmark behavior does not silently regress.

| Concept | Meaning |
| ------- | ------- |
| **`known_nonblocking` / `policy_allowed_execution`** | DashClaw allowed work before an approval gate; the runtime can still be **healthy**. It is **not** “broken stack” for `overall_pass`. |
| **`overall_strict_pass`** | Use when you need **ideal-path-only** evaluation: every rehearsal has `outcome_class: pass` (synthetic + full live approval-gated path). Drops to `false` when the live run is classified `known_nonblocking`. |
| **`overall_pass`** | `true` when **no `hard_failure`** — appropriate default for “is anything actually wrong?” |
| **Synthetic isolation** | Golden path / benchmark synthetic commands send `rehearsal_mode` + `skip_runtime_publish` so the control plane **does not XADD** to `jarvis.commands`, avoiding false collisions with a live coordinator/executor on the same machine. `13` can optionally verify **XLEN** before/after when Redis is reachable. |

## What still cannot be measured cleanly without more surface area

- **Command Center UI paint time** and **voice overlay** latency — not in this harness (no browser automation).
- **True SSE reconnect after server idle or TCP drop** — not injected here; only sequential client connects.
- **Per-stage live-stack time** inside `14` — wall clock is one number; granular breakdown would require instrumenting that script or new server spans (out of scope for “no architecture change”).
- **Operator cognitive / decision time** — included inside governance event deltas; cannot be separated without explicit UI timestamps.

## Safety

Benchmark scripts use the same **non-destructive** patterns as rehearsals: normal missions, approvals, and receipts — no identity scraping, no data wiping. Do not point at production unless you intend to create real mission rows there.
