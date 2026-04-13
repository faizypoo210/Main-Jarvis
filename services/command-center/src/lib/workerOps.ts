import type { StreamPhase } from "../contexts/ControlPlaneLiveContext";
import type {
  HealthState,
  OperatorUsageResponse,
  OperatorWorkersResponse,
  SystemHealthResponse,
  WorkerRead,
} from "./types";

export type WorkerOpsRow = {
  id: string;
  title: string;
  status: HealthState;
  detail: string;
  lastActivityLabel: string | null;
  evidence: string;
  /** From worker metadata ready_state / readiness_reason when present. */
  readinessTag?: string;
  readinessDetail?: string | null;
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

function mapWorkerStatus(s: string): HealthState {
  const x = s.toLowerCase();
  if (x === "healthy") return "healthy";
  if (x === "degraded" || x === "starting") return "degraded";
  if (x === "offline" || x === "stopped") return "offline";
  return "unknown";
}

function readinessFromMeta(meta: Record<string, unknown> | null | undefined): {
  tag: string;
  detail: string | null;
} {
  if (!meta || typeof meta !== "object") return { tag: "", detail: null };
  const rs = meta.ready_state;
  if (typeof rs !== "string" || !rs.trim()) return { tag: "", detail: null };
  const raw = rs.trim().toLowerCase();
  const reason = typeof meta.readiness_reason === "string" ? meta.readiness_reason.trim() : "";
  const short = reason.length > 160 ? `${reason.slice(0, 157)}…` : reason;
  if (raw === "ready") return { tag: "Ready", detail: short || "Reports ready for assigned role." };
  if (raw === "not_ready") return { tag: "Not ready", detail: short || null };
  if (raw === "degraded") return { tag: "Degraded", detail: short || null };
  return { tag: raw, detail: short || null };
}

function rowFromRegistry(w: WorkerRead, staleThresholdMin: number): WorkerOpsRow {
  const st = mapWorkerStatus(w.status);
  const hb = w.last_heartbeat_at;
  const ms = msSince(hb);
  const thrMs = staleThresholdMin * 60 * 1000;
  let status: HealthState = st;
  if (ms != null && ms > thrMs) {
    status = "offline";
  } else if (ms != null && ms > thrMs / 2 && st === "healthy") {
    status = "degraded";
  }
  const metaObj = w.meta && typeof w.meta === "object" ? (w.meta as Record<string, unknown>) : null;
  const metaKeys = metaObj ? Object.keys(metaObj).filter((k) => k !== "readiness_reason").slice(0, 6) : [];
  const metaHint = metaKeys.length ? ` · meta: ${metaKeys.join(", ")}` : "";
  const r = readinessFromMeta(metaObj);
  return {
    id: `reg:${w.worker_type}:${w.instance_id}`,
    title: `${w.name} (${w.worker_type})`,
    status,
    detail: `${w.status}${w.last_error ? ` — ${String(w.last_error).slice(0, 200)}` : ""}${metaHint}`,
    lastActivityLabel: hb ? new Date(hb).toLocaleString() : "No heartbeat yet",
    evidence: `Direct: GET /operator/workers · instance ${w.instance_id}`,
    readinessTag: r.tag || undefined,
    readinessDetail: r.detail,
  };
}

function hasRegistryType(workers: OperatorWorkersResponse | null, t: string): boolean {
  if (!workers?.workers?.length) return false;
  return workers.workers.some((w) => w.worker_type === t);
}

export function buildWorkerRows(
  streamPhase: StreamPhase,
  streamError: string | null,
  usage: OperatorUsageResponse | null,
  health: SystemHealthResponse | null,
  registry: OperatorWorkersResponse | null
): WorkerOpsRow[] {
  const rows: WorkerOpsRow[] = [];
  const staleMin = registry?.stale_threshold_minutes ?? health?.worker_registry?.threshold_minutes ?? 15;

  if (registry && registry.workers.length > 0) {
    for (const w of registry.workers) {
      rows.push(rowFromRegistry(w, staleMin));
    }
  }

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

  if (!hasRegistryType(registry, "coordinator")) {
    const coord = inferFromRecency(
      "Command intake",
      usage?.last_mission_event_at ?? null,
      15 * 60 * 1000,
      24 * 60 * 60 * 1000
    );
    rows.push({
      id: "coordinator",
      title: "Coordinator (inferred)",
      status: coord.status,
      detail: coord.note,
      lastActivityLabel: usage?.last_mission_event_at
        ? new Date(usage.last_mission_event_at).toLocaleString()
        : null,
      evidence: "Inferred from latest mission_events — no registry row for coordinator.",
    });
  }

  if (!hasRegistryType(registry, "executor")) {
    const exec = inferFromRecency(
      "Executor",
      usage?.last_openclaw_execution_at ?? null,
      30 * 60 * 1000,
      48 * 60 * 60 * 1000
    );
    rows.push({
      id: "executor",
      title: "Executor (OpenClaw) (inferred)",
      status: exec.status,
      detail: exec.note,
      lastActivityLabel: usage?.last_openclaw_execution_at
        ? new Date(usage.last_openclaw_execution_at).toLocaleString()
        : null,
      evidence: "Inferred from latest openclaw_execution receipt — no registry row for executor.",
    });
  }

  return rows;
}
