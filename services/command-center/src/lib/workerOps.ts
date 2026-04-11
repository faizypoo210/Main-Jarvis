import type { StreamPhase } from "../contexts/ControlPlaneLiveContext";
import type { HealthState, OperatorUsageResponse, SystemHealthResponse } from "./types";

export type WorkerOpsRow = {
  id: string;
  title: string;
  status: HealthState;
  detail: string;
  lastActivityLabel: string | null;
  evidence: string;
};

function msSince(iso: string | null): number | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  return Date.now() - t;
}

function inferFromRecency(
  label: string,
  iso: string | null,
  healthyMaxMs: number,
  degradedMaxMs: number
): { status: HealthState; note: string } {
  const ms = msSince(iso);
  if (ms == null) {
    return { status: "unknown", note: "No timeline signal in control plane yet." };
  }
  if (ms <= healthyMaxMs) {
    return { status: "healthy", note: `${label} recent (inferred from control-plane timestamps).` };
  }
  if (ms <= degradedMaxMs) {
    return { status: "degraded", note: `${label} quiet — last seen ${Math.round(ms / 60000)} min ago.` };
  }
  return {
    status: "offline",
    note: `${label} stale — last seen ${Math.round(ms / 3600000)} h ago. Process may be down or idle.`,
  };
}

export function buildWorkerRows(
  streamPhase: StreamPhase,
  streamError: string | null,
  usage: OperatorUsageResponse | null,
  health: SystemHealthResponse | null
): WorkerOpsRow[] {
  const rows: WorkerOpsRow[] = [];

  const cp = health?.control_plane.status ?? "unknown";
  rows.push({
    id: "control_plane",
    title: "Control plane",
    status: cp,
    detail: health?.control_plane.detail ?? "HTTP status from this browser.",
    lastActivityLabel: health?.checked_at ? "Snapshot" : null,
    evidence: "GET /api/v1/system/health (authoritative).",
  });

  let sseStatus: HealthState = "unknown";
  let sseDetail = "";
  if (streamPhase === "live") {
    sseStatus = "healthy";
    sseDetail = "SSE stream open.";
  } else if (streamPhase === "reconnecting") {
    sseStatus = "degraded";
    sseDetail = "Reconnecting to live stream.";
  } else {
    sseStatus = "offline";
    sseDetail = streamError ?? "Stream offline.";
  }
  rows.push({
    id: "sse",
    title: "Live updates (SSE)",
    status: sseStatus,
    detail: sseDetail,
    lastActivityLabel: streamPhase === "live" ? "Connected" : null,
    evidence: "GET /api/v1/updates/stream from this browser (inferred).",
  });

  const redis = health?.redis.status ?? "unknown";
  rows.push({
    id: "redis",
    title: "Redis (command bus)",
    status: redis,
    detail: health?.redis.detail ?? "",
    lastActivityLabel: health?.checked_at ? "Probed" : null,
    evidence: "PING from control plane (same host as API).",
  });

  const gw = health?.openclaw_gateway.status ?? "unknown";
  rows.push({
    id: "openclaw_gateway",
    title: "OpenClaw gateway",
    status: gw,
    detail: health?.openclaw_gateway.detail ?? "",
    lastActivityLabel: health?.checked_at ? "Probed" : null,
    evidence: "HTTP probe from control plane (configurable URL).",
  });

  const coord = inferFromRecency(
    "Command intake",
    usage?.last_mission_event_at ?? null,
    15 * 60 * 1000,
    24 * 60 * 60 * 1000
  );
  rows.push({
    id: "coordinator",
    title: "Coordinator",
    status: coord.status,
    detail: coord.note,
    lastActivityLabel: usage?.last_mission_event_at
      ? new Date(usage.last_mission_event_at).toLocaleString()
      : null,
    evidence: "Inferred from latest mission_events timestamp (not a process heartbeat).",
  });

  const exec = inferFromRecency(
    "Executor",
    usage?.last_openclaw_execution_at ?? null,
    30 * 60 * 1000,
    48 * 60 * 60 * 1000
  );
  rows.push({
    id: "executor",
    title: "Executor (OpenClaw)",
    status: exec.status,
    detail: exec.note,
    lastActivityLabel: usage?.last_openclaw_execution_at
      ? new Date(usage.last_openclaw_execution_at).toLocaleString()
      : null,
    evidence: "Inferred from latest openclaw_execution receipt (not a direct worker ping).",
  });

  return rows;
}
