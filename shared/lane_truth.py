"""Canonical lane truth (v1) — one vocabulary for mission routing vs OpenClaw model target.

**Direct truth** (stored):
- Mission routing: ``requested_lane``, ``actual_lane``, ``fallback_applied``, ``reason_code``,
  ``reason_summary``, optional ``fallback_reason_code`` when ``fallback_applied`` (stable code).
- Executor: ``openclaw_model_lane`` — for receipts, derived from ``routing.requested_lane`` when set
  (``gateway`` / ``local_fast`` → ``gateway`` / ``local``); otherwise falls back to the configured
  default gateway model string (``ollama/…`` → ``local``, else ``gateway``). ``gateway_model`` is
  still the string from ``openclaw.json``.

**Not the same thing:**
- ``routing.actual_lane`` = mission executor *class* (today always ``gateway`` — OpenClaw only).
- Receipt ``openclaw_model_lane`` aligns with ``requested_lane`` when present; fallback reflects the
  configured default agent model when routing is absent.
- Voice may call Ollama **directly** for acks; that never appears on mission ``routing_decided``
  or executor receipts.

**Derived block:** ``execution_meta.lane_truth`` reconciles routing snapshot + ``openclaw_model_lane``
for receipts and UI (schema_version ``1``).
"""

from __future__ import annotations

from typing import Any

LANE_TRUTH_SCHEMA_VERSION = "1"

# Mission code path: only the OpenClaw executor consumes jarvis.execution in this repo.
MISSION_EXECUTION_PATH_OPENCLAW = "openclaw_executor"


def build_lane_truth_block(
    *,
    routing: dict[str, Any] | None,
    openclaw_model_lane: str,
) -> dict[str, Any]:
    """Build ``execution_meta.lane_truth`` — JSON-safe, no secrets.

    ``openclaw_model_lane`` argument is the configured default-gateway heuristic used when
    ``routing.requested_lane`` is absent or unknown.
    """
    r = routing or {}
    req = str(r.get("requested_lane") or "")
    req_norm = req.strip().lower()
    r_act = str(r.get("actual_lane") or "")
    fb = bool(r.get("fallback_applied"))
    rc = str(r.get("reason_code") or "")
    rs = str(r.get("reason_summary") or "")
    frc_raw = r.get("fallback_reason_code")
    frc_s = str(frc_raw).strip() if frc_raw is not None else ""
    fallback_code = frc_s if frc_s else (rc if fb else "")

    if req_norm == "gateway":
        oml = "gateway"
    elif req_norm == "local_fast":
        oml = "local"
    else:
        oml = openclaw_model_lane

    out: dict[str, Any] = {
        "schema_version": LANE_TRUTH_SCHEMA_VERSION,
        "requested_lane": req,
        "routing_actual_lane": r_act,
        "fallback_applied": fb,
        "fallback_reason_code": fallback_code if fb else None,
        "reason_code": rc if rc else None,
        "openclaw_model_lane": oml,
        "mission_execution_path": MISSION_EXECUTION_PATH_OPENCLAW,
    }
    if rs:
        out["reason_summary"] = rs[:500]
    return out
