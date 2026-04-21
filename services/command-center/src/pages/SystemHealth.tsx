import { useMemo } from "react";
import { OperatorHealthCard } from "../components/operator/OperatorHealthCard";
import { useShellHealth } from "../contexts/ShellHealthContext";
import { useOperatorWorkers } from "../hooks/useOperatorWorkers";
import { formatRelativeTime } from "../lib/format";
import { sseStatus, workerRegistryStatus } from "../lib/operatorRuntimeHealth";
import type { HealthState, WorkerRead } from "../lib/types";

function mapWorkerReportedStatus(s: string): HealthState {
  const x = s.toLowerCase();
  if (x === "healthy") return "healthy";
  if (x === "degraded" || x === "starting") return "degraded";
  if (x === "offline" || x === "stopped") return "offline";
  return "unknown";
}

function healthRank(s: HealthState): number {
  switch (s) {
    case "offline":
      return 4;
    case "degraded":
      return 3;
    case "unknown":
      return 2;
    case "healthy":
      return 1;
    default:
      return 0;
  }
}

function worstHealth(a: HealthState, b: HealthState): HealthState {
  return healthRank(a) >= healthRank(b) ? a : b;
}

function pickWorkerForType(workers: WorkerRead[], workerType: string): WorkerRead | null {
  const matches = workers.filter((w) => w.worker_type === workerType);
  if (matches.length === 0) return null;
  return matches.reduce((best, w) => {
    const tw = w.last_heartbeat_at ? Date.parse(w.last_heartbeat_at) : 0;
    const tb = best.last_heartbeat_at ? Date.parse(best.last_heartbeat_at) : 0;
    return tw >= tb ? w : best;
  });
}

function effectiveWorkerHealth(w: WorkerRead, staleThresholdMin: number): HealthState {
  const reported = mapWorkerReportedStatus(w.status);
  if (!w.last_heartbeat_at) {
    return reported === "healthy" ? "degraded" : reported;
  }
  const ms = Date.now() - Date.parse(w.last_heartbeat_at);
  if (Number.isNaN(ms)) return reported;
  const thrMs = staleThresholdMin * 60 * 1000;
  if (ms > thrMs) return "offline";
  if (ms > thrMs / 2 && reported === "healthy") return "degraded";
  return reported;
}

export function SystemHealth() {
  const { live, systemHealth, hb } = useShellHealth();
  const { data, error, loading } = systemHealth;
  const {
    data: workersData,
    error: workersError,
    loading: workersLoading,
  } = useOperatorWorkers(30000);

  const sse = useMemo(
    () => sseStatus(live.streamPhase, live.streamError),
    [live.streamPhase, live.streamError]
  );

  const localModel = import.meta.env.VITE_JARVIS_LOCAL_MODEL?.trim() || "(not set)";
  const cloudModel = import.meta.env.VITE_JARVIS_CLOUD_MODEL?.trim() || "(not set)";
  const localModelDisplay = localModel === "(not set)" ? "(not set)" : `${localModel} (configured)`;
  const cloudModelDisplay = cloudModel === "(not set)" ? "(not set)" : `${cloudModel} (configured)`;

  const runtimeCard = useMemo(() => {
    const staleMin = workersData?.stale_threshold_minutes ?? data?.worker_registry.threshold_minutes ?? 15;
    const list = workersData?.workers ?? [];

    const ex = pickWorkerForType(list, "executor");
    const co = pickWorkerForType(list, "coordinator");

    const exHealth: HealthState = ex ? effectiveWorkerHealth(ex, staleMin) : "unknown";
    const coHealth: HealthState = co ? effectiveWorkerHealth(co, staleMin) : "unknown";

    let overall: HealthState = worstHealth(exHealth, coHealth);
    if (workersError) overall = worstHealth(overall, "degraded");
    else if (workersLoading && !workersData) overall = "unknown";

    const roleLine = (label: string, w: WorkerRead | null) => {
      if (!w) {
        return (
          <p key={label} className="text-[10px] leading-snug text-[var(--text-muted)]">
            <span className="font-medium text-[var(--text-secondary)]">{label}:</span> unregistered
          </p>
        );
      }
      const hb = w.last_heartbeat_at
        ? formatRelativeTime(w.last_heartbeat_at)
        : "no heartbeat yet";
      return (
        <p key={`${label}-${w.instance_id}`} className="text-[10px] leading-snug text-[var(--text-muted)]">
          <span className="font-medium text-[var(--text-secondary)]">{label}:</span>{" "}
          <span className="text-[var(--text-primary)]">{w.status}</span>
          {" · "}
          last heartbeat {hb}
        </p>
      );
    };

    const detailParts: string[] = [
      `Local ${localModelDisplay} · Cloud ${cloudModelDisplay}`,
      workersError
        ? workersError
        : workersLoading && !workersData
          ? "Loading worker registry…"
          : "Model labels are build-time Vite config; executor/coordinator from GET /api/v1/operator/workers.",
    ];

    return {
      overall,
      detail: detailParts.join(" — "),
      footer: (
        <div className="space-y-1.5 border-t border-[var(--bg-border)]/60 pt-2">
          <p className="text-[10px] leading-snug text-[var(--text-muted)]">
            <span className="font-medium text-[var(--text-secondary)]">Local model:</span>{" "}
            <span className="font-mono text-[9px] text-[var(--text-primary)]">{localModelDisplay}</span>
          </p>
          <p className="text-[10px] leading-snug text-[var(--text-muted)]">
            <span className="font-medium text-[var(--text-secondary)]">Cloud model:</span>{" "}
            <span className="font-mono text-[9px] text-[var(--text-primary)]">{cloudModelDisplay}</span>
          </p>
          <p className="text-[9px] leading-snug text-[var(--text-muted)]">
            Model names reflect build-time config. Restart Command Center after changing VITE_JARVIS_LOCAL_MODEL or
            VITE_JARVIS_CLOUD_MODEL.
          </p>
          {roleLine("Executor", ex)}
          {roleLine("Coordinator", co)}
          <p className="text-[10px] leading-snug text-[var(--text-muted)]">
            <span className="font-medium text-[var(--text-secondary)]">Lane routing:</span> coming soon
          </p>
        </div>
      ),
    };
  }, [
    workersData,
    workersError,
    workersLoading,
    data?.worker_registry.threshold_minutes,
    localModelDisplay,
    cloudModelDisplay,
  ]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      {error ? (
        <div
          className="shrink-0 border-b border-[var(--status-amber)]/30 bg-[var(--status-amber)]/10 px-4 py-2 text-center text-xs text-[var(--status-amber)] md:px-6"
          role="status"
        >
          {error}
        </div>
      ) : null}
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4 md:px-6">
        <p className="mb-4 max-w-2xl text-xs leading-relaxed text-[var(--text-muted)]">
          Control-plane dependencies (API, Postgres, Redis) are probed on this host. OpenClaw/Ollama rows
          only reflect execution truth when a URL is configured or inferred from worker metadata — not
          implicit localhost. Plus this browser&apos;s live stream. Operations visibility only.
        </p>
        {loading && !data ? (
          <p className="text-sm text-[var(--text-muted)]">Loading health snapshot…</p>
        ) : null}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <OperatorHealthCard
            title="Runtime"
            status={runtimeCard.overall}
            detail={runtimeCard.detail}
            footer={runtimeCard.footer}
          />
          {data ? (
            <>
              <OperatorHealthCard
                title="Control plane API"
                status={data.control_plane.status}
                detail={data.control_plane.detail}
                footer={
                  <p className="text-[10px] text-[var(--text-muted)]">
                    Last checked {formatRelativeTime(data.checked_at)}
                  </p>
                }
              />
              <OperatorHealthCard
                title="PostgreSQL"
                status={data.postgres.status}
                detail={data.postgres.detail}
                footer={
                  <p className="text-[10px] text-[var(--text-muted)]">
                    Snapshot {formatRelativeTime(data.checked_at)}
                  </p>
                }
              />
              <OperatorHealthCard
                title="Redis"
                status={data.redis.status}
                detail={data.redis.detail}
                footer={
                  <p className="text-[10px] text-[var(--text-muted)]">
                    Used for streams / coordinator path (same probe as API host).
                  </p>
                }
              />
              <OperatorHealthCard
                title="OpenClaw gateway"
                status={data.openclaw_gateway.status}
                detail={data.openclaw_gateway.detail}
                footer={
                  <p className="text-[10px] text-[var(--text-muted)]">
                    {data.openclaw_gateway.probe_source ? (
                      <>
                        Scope:{" "}
                        <span className="font-mono text-[9px]">{data.openclaw_gateway.probe_source}</span>
                        .{" "}
                      </>
                    ) : null}
                    HTTP GET from the control-plane process. Set{" "}
                    <code className="font-mono text-[9px]">JARVIS_HEALTH_OPENCLAW_GATEWAY_URL</code> or
                    worker <code className="font-mono text-[9px]">gateway_health_url</code> metadata.
                  </p>
                }
              />
              <OperatorHealthCard
                title="Ollama"
                status={data.ollama.status}
                detail={data.ollama.detail}
                footer={
                  <p className="text-[10px] text-[var(--text-muted)]">
                    {data.ollama.probe_source ? (
                      <>
                        Scope:{" "}
                        <span className="font-mono text-[9px]">{data.ollama.probe_source}</span>.{" "}
                      </>
                    ) : null}
                    Typical probe path <code className="font-mono text-[9px]">/api/tags</code> via{" "}
                    <code className="font-mono text-[9px]">JARVIS_HEALTH_OLLAMA_URL</code> or worker{" "}
                    <code className="font-mono text-[9px]">ollama_health_url</code>.
                  </p>
                }
              />
              <OperatorHealthCard
                title="Worker registry"
                status={workerRegistryStatus(data.worker_registry)}
                detail={
                  data.worker_registry.registered_total === 0
                    ? "No workers registered yet (workers POST register/heartbeat with API key)."
                    : `${data.worker_registry.healthy_heartbeat} fresh heartbeat(s), ${data.worker_registry.stale_or_absent} stale or missing within ${data.worker_registry.threshold_minutes}m threshold. Role readiness: ${data.worker_registry.readiness_ready ?? 0} ready, ${data.worker_registry.readiness_not_ready ?? 0} not ready, ${data.worker_registry.readiness_degraded ?? 0} degraded.`
                }
                footer={
                  <p className="text-[10px] text-[var(--text-muted)]">
                    Direct rows in <code className="font-mono text-[9px]">workers</code> table. See Workers
                    page for detail.
                  </p>
                }
              />
            </>
          ) : null}
          <OperatorHealthCard
            title="Live updates (SSE)"
            status={sse.status}
            detail={sse.detail}
            footer={
              <p className="text-[10px] text-[var(--text-muted)]">
                Browser connection to <code className="font-mono text-[9px]">/api/v1/updates/stream</code>.
                Phase: <span className="text-[var(--text-secondary)]">{live.streamPhase}</span>
              </p>
            }
          />
          <OperatorHealthCard
            title="Heartbeat supervision"
            status={
              hb.loading && !hb.data
                ? "degraded"
                : hb.error
                  ? "offline"
                  : (hb.data?.open_count ?? 0) > 0
                    ? "degraded"
                    : "healthy"
            }
            detail={
              hb.error
                ? hb.error
                : hb.data
                  ? hb.data.open_count > 0
                    ? `${hb.data.open_count} open finding(s). Rule-based checks from the control plane — not process-level certainty unless noted.`
                    : "No open supervision findings. The heartbeat loop only surfaces explicit, actionable conditions."
                  : hb.loading
                    ? "Loading heartbeat snapshot…"
                    : null
            }
            footer={
              <p className="text-[10px] text-[var(--text-muted)]">
                API: <code className="font-mono text-[9px]">GET /api/v1/operator/heartbeat</code>
              </p>
            }
          />
        </div>
        {!loading && !data && !error ? (
          <p className="mt-6 text-sm text-[var(--text-muted)]">No health data yet.</p>
        ) : null}
      </div>
    </div>
  );
}
