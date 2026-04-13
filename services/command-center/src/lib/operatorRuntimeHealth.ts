import type { HealthState, SystemHealthResponse, WorkerRegistrySummary } from "./types";

export function workerRegistryStatus(wr: WorkerRegistrySummary): HealthState {
  if (wr.registered_total === 0) return "unknown";
  const notReady = wr.readiness_not_ready ?? 0;
  const degradedReady = wr.readiness_degraded ?? 0;
  if (wr.stale_or_absent === 0) {
    if (notReady > 0) return "degraded";
    if (degradedReady > 0) return "degraded";
    return "healthy";
  }
  if (wr.healthy_heartbeat > 0) return "degraded";
  return "offline";
}

export function sseStatus(phase: string, err: string | null): { status: HealthState; detail: string } {
  if (phase === "live") return { status: "healthy", detail: "Stream open; receiving live mission updates." };
  if (phase === "reconnecting") {
    return { status: "degraded", detail: err ?? "Reconnecting to the live stream." };
  }
  return { status: "offline", detail: err ?? "Live stream not connected." };
}

export type ShellRuntimeSummary = {
  overall: "ok" | "attention" | "critical";
  /** System health GET failed (no snapshot). */
  systemHealthFetchFailed: boolean;
  pills: {
    cp: { state: HealthState; short: string };
    sse: { state: HealthState; short: string };
    wr: { state: HealthState; short: string };
    hb: { state: HealthState; short: string; openCount: number | null };
  };
  /** Max two lines for a subtle shell banner. */
  bannerLines: string[];
};

function healthStateToShort(state: HealthState, kind: "cp" | "sse" | "wr" | "hb"): string {
  switch (state) {
    case "healthy":
      return kind === "sse" ? "LIVE" : "OK";
    case "degraded":
      return kind === "sse" ? "REC" : "DEG";
    case "offline":
      return "OFF";
    default:
      return kind === "wr" ? "—" : "?";
  }
}

export function deriveShellRuntimeSummary(args: {
  streamPhase: string;
  streamError: string | null;
  systemHealthError: string | null;
  systemHealthLoading: boolean;
  systemHealthData: SystemHealthResponse | null;
  heartbeatError: string | null;
  heartbeatLoading: boolean;
  heartbeatOpenCount: number | null;
}): ShellRuntimeSummary {
  const { streamPhase, streamError, systemHealthError, systemHealthLoading, systemHealthData } = args;
  const sse = sseStatus(streamPhase, streamError);

  let wrState: HealthState = "unknown";
  let wrShort = "—";
  if (systemHealthData) {
    wrState = workerRegistryStatus(systemHealthData.worker_registry);
    const wr = systemHealthData.worker_registry;
    if (wr.registered_total === 0) {
      wrShort = "—";
    } else if (wrState === "healthy") {
      wrShort = "OK";
    } else {
      wrShort = healthStateToShort(wrState, "wr");
    }
  }

  let hbState: HealthState = "unknown";
  let hbOpen: number | null = null;
  if (args.heartbeatError) {
    hbState = "offline";
  } else if (args.heartbeatLoading && args.heartbeatOpenCount == null) {
    hbState = "unknown";
  } else if ((args.heartbeatOpenCount ?? 0) > 0) {
    hbState = "degraded";
    hbOpen = args.heartbeatOpenCount;
  } else {
    hbState = "healthy";
  }

  const cpState: HealthState = systemHealthError
    ? "offline"
    : systemHealthLoading && !systemHealthData
      ? "unknown"
      : (systemHealthData?.control_plane.status ?? "unknown");

  const pills = {
    cp: {
      state: cpState,
      short: systemHealthLoading && !systemHealthData ? "…" : healthStateToShort(cpState, "cp"),
    },
    sse: { state: sse.status, short: healthStateToShort(sse.status, "sse") },
    wr: { state: wrState, short: wrShort },
    hb: {
      state: hbState,
      short:
        hbOpen != null && hbOpen > 0
          ? `!${hbOpen}`
          : hbState === "healthy"
            ? "OK"
            : hbState === "offline"
              ? "ERR"
              : args.heartbeatLoading
                ? "…"
                : "?",
      openCount: hbOpen,
    },
  };

  const bannerLines: string[] = [];
  if (systemHealthError) {
    bannerLines.push("Control plane health snapshot unavailable (browser could not load /api/v1/system/health).");
  } else if (systemHealthData?.control_plane.status === "offline") {
    bannerLines.push("Control plane API reports offline or unreachable from the server.");
  }
  if (sse.status === "offline") {
    bannerLines.push("Live mission stream (SSE) is not connected.");
  } else if (sse.status === "degraded") {
    bannerLines.push("Live stream reconnecting — mission list may be stale briefly.");
  }
  if (args.heartbeatError) {
    bannerLines.push("Heartbeat supervision snapshot failed to load.");
  } else if ((args.heartbeatOpenCount ?? 0) > 0) {
    bannerLines.push(
      `${args.heartbeatOpenCount} open supervision finding(s) — rule-based checks, not process-level certainty.`
    );
  }
  if (systemHealthData && wrState === "offline" && systemHealthData.worker_registry.registered_total > 0) {
    bannerLines.push("Worker registry reports stale or missing heartbeats.");
  }
  if (systemHealthData?.control_plane.status === "degraded") {
    bannerLines.push("Control plane reports degraded (Postgres/Redis or probes — see System Health).");
  }
  if (systemHealthData && wrState === "degraded") {
    bannerLines.push("Some workers look stale within the registry threshold.");
  }

  const trimmedBanner = bannerLines.slice(0, 2);

  let overall: ShellRuntimeSummary["overall"] = "ok";
  if (systemHealthError || systemHealthData?.control_plane.status === "offline" || sse.status === "offline") {
    overall = "critical";
  } else if (
    sse.status === "degraded" ||
    systemHealthData?.control_plane.status === "degraded" ||
    wrState === "degraded" ||
    wrState === "offline" ||
    (args.heartbeatOpenCount ?? 0) > 0 ||
    args.heartbeatError
  ) {
    overall = "attention";
  }

  return {
    overall,
    systemHealthFetchFailed: Boolean(systemHealthError),
    pills,
    bannerLines: trimmedBanner,
  };
}
