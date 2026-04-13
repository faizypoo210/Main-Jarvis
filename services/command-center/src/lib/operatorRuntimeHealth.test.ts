import { describe, expect, it } from "vitest";
import { deriveShellRuntimeSummary, workerRegistryStatus } from "./operatorRuntimeHealth";
import type { SystemHealthResponse } from "./types";

describe("workerRegistryStatus", () => {
  it("returns degraded when any worker reports not_ready but heartbeats are fresh", () => {
    expect(
      workerRegistryStatus({
        registered_total: 2,
        healthy_heartbeat: 2,
        stale_or_absent: 0,
        threshold_minutes: 15,
        readiness_ready: 1,
        readiness_not_ready: 1,
        readiness_degraded: 0,
      })
    ).toBe("degraded");
  });

  it("returns healthy when all workers are ready and heartbeats are fresh", () => {
    expect(
      workerRegistryStatus({
        registered_total: 1,
        healthy_heartbeat: 1,
        stale_or_absent: 0,
        threshold_minutes: 15,
        readiness_ready: 1,
        readiness_not_ready: 0,
        readiness_degraded: 0,
      })
    ).toBe("healthy");
  });
});

function baseHealth(over: Partial<SystemHealthResponse> = {}): SystemHealthResponse {
  const ch = { status: "healthy" as const, detail: "ok", probe_source: "control_plane_local" as const };
  return {
    checked_at: "2026-01-01T00:00:00Z",
    control_plane: ch,
    postgres: ch,
    redis: ch,
    openclaw_gateway: { status: "unknown", detail: null, probe_source: "unknown" },
    ollama: { status: "unknown", detail: null, probe_source: "unknown" },
    worker_registry: {
      registered_total: 0,
      healthy_heartbeat: 0,
      stale_or_absent: 0,
      threshold_minutes: 15,
    },
    ...over,
  };
}

describe("deriveShellRuntimeSummary", () => {
  it("flags attention when worker registry has registered workers but heartbeats are stale", () => {
    const s = deriveShellRuntimeSummary({
      streamPhase: "live",
      streamError: null,
      systemHealthError: null,
      systemHealthLoading: false,
      systemHealthData: baseHealth({
        worker_registry: {
          registered_total: 2,
          healthy_heartbeat: 0,
          stale_or_absent: 2,
          threshold_minutes: 15,
          readiness_ready: 0,
          readiness_not_ready: 0,
          readiness_degraded: 0,
        },
      }),
      heartbeatError: null,
      heartbeatLoading: false,
      heartbeatOpenCount: 0,
    });
    expect(s.overall).toBe("attention");
    expect(s.bannerLines.some((l) => /stale or missing heartbeats/i.test(l))).toBe(true);
  });

  it("surfaces critical when system health fetch failed", () => {
    const s = deriveShellRuntimeSummary({
      streamPhase: "live",
      streamError: null,
      systemHealthError: "network",
      systemHealthLoading: false,
      systemHealthData: null,
      heartbeatError: null,
      heartbeatLoading: false,
      heartbeatOpenCount: 0,
    });
    expect(s.overall).toBe("critical");
    expect(s.systemHealthFetchFailed).toBe(true);
    expect(s.bannerLines.length).toBeGreaterThan(0);
  });
});
