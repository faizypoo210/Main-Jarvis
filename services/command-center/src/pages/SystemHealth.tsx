import { useMemo } from "react";
import { OperatorHealthCard } from "../components/operator/OperatorHealthCard";
import { useShellHealth } from "../contexts/ShellHealthContext";
import { formatRelativeTime } from "../lib/format";
import { sseStatus, workerRegistryStatus } from "../lib/operatorRuntimeHealth";
export function SystemHealth() {
  const { live, systemHealth, hb } = useShellHealth();
  const { data, error, loading } = systemHealth;

  const sse = useMemo(
    () => sseStatus(live.streamPhase, live.streamError),
    [live.streamPhase, live.streamError]
  );

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
                    : `${data.worker_registry.healthy_heartbeat} fresh heartbeat(s), ${data.worker_registry.stale_or_absent} stale or missing within ${data.worker_registry.threshold_minutes}m threshold.`
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
