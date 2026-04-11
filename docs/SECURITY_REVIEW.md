# Security review (operator / single-machine stack)

Lightweight, **honest** snapshot of how Jarvis is meant to be run today. This is not a formal penetration test or compliance attestation.

## Trust boundaries

| Boundary | What is trusted |
| -------- | ---------------- |
| **Operator device** | The Windows user running Command Center, scripts, and local services is trusted to hold API keys in env and in `%USERPROFILE%\.openclaw\`. |
| **Control plane** | Authoritative for missions, events, approvals, receipts. Clients that know `CONTROL_PLANE_API_KEY` are trusted for mutating APIs and SSE. |
| **PostgreSQL / Redis** | Trusted localhost services; not exposed to the internet by default in the dev layout. |
| **OpenClaw gateway** | Trusted on LAN when `bind: lan`; gateway token gates CLI/WebSocket clients. |
| **DashClaw** | External HTTPS service; coordinator sends **Bearer** token; trust TLS and DashClaw operator account. |
| **Browser / Command Center** | Same-origin dev server (`localhost:5173`); API key embedded via Vite env at dev/build time — **not** suitable as a public website without a different auth model. |

## Single-machine assumptions

- Typical deployment is **one operator PC** running Docker, control plane, coordinator, executor, and gateway.
- **No multi-tenant isolation** is assumed at the application layer; mission rows are not partitioned by untrusted tenants.
- Files under the repo and `%USERPROFILE%\.openclaw\` are readable by the same user; **protect the OS account**.

## SSE / live updates

- SSE runs through the **same FastAPI process** as REST; auth is **`require_api_key`** on `/api/v1/updates/stream`.
- **Assumption:** one control plane instance; no distributed SSE fan-out across machines in-repo.
- Clients that can open the stream with a valid key see **mission events** for all missions that user’s deployment serves.

## Local file / workspace boundary

- `config/workspace/*.md` are **tracked persona mirrors**; live OpenClaw reads `%USERPROFILE%\.openclaw\workspace\main\`.
- **Do not** put secrets in tracked markdown; sync scripts copy content only.

## Approval / governance boundary

- Risky actions are gated by **human approval** (Command Center, voice brief, DashClaw policy).  
- Misconfiguration (e.g. missing DashClaw, permissive guard) can **bypass intent**; security depends on correct **coordinator + DashClaw + control plane** wiring, not UI alone.

## Known remaining risks (in scope for awareness)

| Risk | Mitigation direction |
| ---- | -------------------- |
| **Vite-embedded API key** | Acceptable for local dev only; for any shared or hosted UI, use a backend session or proxy — **out of scope** for this repo’s current architecture. |
| **LAN exposure** | `bind: lan` and firewall rules expose ports to the LAN; use OS firewall + `JARVIS_LAN_IP` discipline. |
| **Default Postgres password** | Documented dev default; change for shared or production-like hosts (`docs/SECRET_ROTATION.md`). |
| **Secrets in shell history** | Avoid `echo $env:...` in shared sessions; prefer User env. |
| **Third-party services** | DashClaw, Composio, model providers — trust their security posture and rotate keys on their consoles. |

## Out of scope (for now)

- Public multi-user SaaS hardening, OAuth for Command Center, rate limiting, audit logging to SIEM, mTLS everywhere, Kubernetes secrets operators, automated secret scanning in CI.
- Formal **CVE** response process (use GitHub security advisories if the project goes public).

## Related docs

- [`SECRET_ROTATION.md`](./SECRET_ROTATION.md) — what to rotate and where it lives.  
- [`FAILURE_MODES.md`](./FAILURE_MODES.md) — operational failure behavior.  
- [`REALTIME_UPDATES.md`](./REALTIME_UPDATES.md) — SSE behavior.
