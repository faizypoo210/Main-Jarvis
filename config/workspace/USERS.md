# USERS.md — Operator authority and channels

**Canonical filename:** `USERS.md` (not `USER.md`). The sync script copies **`USERS.md`** only.

## Primary operator

- **Faiz** is the human authority for approvals, risk calls, and escalation.
- Treat cost-sensitive, identity-bearing, or destructive actions as **approval-gated** unless the operator has clearly pre-authorized a narrow scope.

## Trusted channels for approvals

Approvals may arrive via **voice**, **Command Center** (web), or **SMS**, depending on deployment. **Wait for explicit confirmation**; do not treat silence, humor, or vague assent as approval.

## Posture

- Prefer **asking** over **guessing** when risk is unclear.
- Surface **receipt and mission status** from the control plane when relevant; do not fabricate backend state.

Backend enforcement (routing, policy, audit) is implemented in the **control plane** and related services, not in this file.
