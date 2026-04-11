import { useMemo } from "react";
import { OperatorHealthCard } from "../components/operator/OperatorHealthCard";
import { useControlPlaneLive } from "../hooks/useControlPlane";
import { useSystemHealth } from "../hooks/useSystemHealth";
import { formatRelativeTime } from "../lib/format";
import type { HealthState } from "../lib/types";

function sseStatus(phase: string, err: string | null): { status: HealthState; detail: string } {
  if (phase === "live") return { status: "healthy", detail: "Stream open; receiving live mission updates." };
  if (phase === "reconnecting") {
    return { status: "degraded", detail: err ?? "Reconnecting to the live stream." };
  }
  return { status: "offline", detail: err ?? "Live stream not connected." };
}

export function SystemHealth() {
  const live = useControlPlaneLive();
  const { data, error, loading } = useSystemHealth();

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
          Summary of services the control plane can probe from the server, plus this browser&apos;s live
          stream. Values are for operations visibility — not a full observability stack.
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
                    HTTP GET from control plane. Override with{" "}
                    <code className="font-mono text-[9px]">JARVIS_HEALTH_OPENCLAW_GATEWAY_URL</code> on
                    the server if needed.
                  </p>
                }
              />
              <OperatorHealthCard
                title="Ollama"
                status={data.ollama.status}
                detail={data.ollama.detail}
                footer={
                  <p className="text-[10px] text-[var(--text-muted)]">
                    Default probe: <code className="font-mono text-[9px]">/api/tags</code>. Override with{" "}
                    <code className="font-mono text-[9px]">JARVIS_HEALTH_OLLAMA_URL</code>.
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
        </div>
        {!loading && !data && !error ? (
          <p className="mt-6 text-sm text-[var(--text-muted)]">No health data yet.</p>
        ) : null}
      </div>
    </div>
  );
}
