import { useEffect, useMemo, useState } from "react";
import { useControlPlaneLive } from "../contexts/ControlPlaneLiveContext";
import type { Approval, Mission, MissionEvent } from "../lib/types";

export { useControlPlaneLive } from "../contexts/ControlPlaneLiveContext";
export type { StreamPhase } from "../contexts/ControlPlaneLiveContext";
export { useResolveApprovalAction } from "./useResolveApprovalAction";
export type {
  LastResolvedApproval,
  ResolveApprovalSuccessOptions,
} from "./useResolveApprovalAction";

export function useMissions(params?: {
  status?: string;
  limit?: number;
}): {
  missions: Mission[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
} {
  const ctx = useControlPlaneLive();
  const missions = useMemo(() => {
    let m = ctx.missions;
    if (params?.status) {
      m = m.filter((x) => x.status === params.status);
    }
    if (params?.limit != null) {
      m = m.slice(0, params.limit);
    }
    return m;
  }, [ctx.missions, params?.status, params?.limit]);

  useEffect(() => {
    if (ctx.streamConnected) return;
    const id = window.setInterval(() => void ctx.refetchMissions(), 15000);
    return () => clearInterval(id);
  }, [ctx.streamConnected, ctx.refetchMissions]);

  return {
    missions,
    loading: ctx.missionsLoading,
    error: ctx.missionsError,
    refetch: ctx.refetchMissions,
  };
}

export function usePendingApprovals(params?: { pollIntervalMs?: number }): {
  approvals: Approval[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
} {
  const ctx = useControlPlaneLive();
  const pollIntervalMs = params?.pollIntervalMs ?? 8000;

  useEffect(() => {
    if (ctx.streamConnected) return;
    const id = window.setInterval(() => void ctx.refetchPendingApprovals(), pollIntervalMs);
    return () => clearInterval(id);
  }, [ctx.streamConnected, pollIntervalMs, ctx.refetchPendingApprovals]);

  return {
    approvals: ctx.pendingApprovals,
    loading: ctx.pendingLoading,
    error: ctx.pendingError,
    refetch: ctx.refetchPendingApprovals,
  };
}

/** Mission detail + timeline: hydrated once, then live via SSE; polls when stream is down. */
export function usePolledMissionDetail(missionId: string | null, pollIntervalMs = 8000): {
  mission: Mission | null;
  events: MissionEvent[];
  loading: boolean;
  error: string | null;
} {
  const ctx = useControlPlaneLive();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!missionId?.trim()) {
      setError(null);
      return;
    }
    let cancelled = false;
    setError(null);
    void (async () => {
      try {
        await ctx.bootstrapMission(missionId);
      } catch (e: unknown) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [missionId, ctx.bootstrapMission]);

  useEffect(() => {
    if (!missionId?.trim() || ctx.streamConnected) return;
    const id = window.setInterval(() => void ctx.bootstrapMission(missionId), pollIntervalMs);
    return () => clearInterval(id);
  }, [missionId, ctx.streamConnected, pollIntervalMs, ctx.bootstrapMission]);

  const mission = missionId
    ? ctx.missionById[missionId] ?? ctx.missions.find((m) => m.id === missionId) ?? null
    : null;
  const events = missionId ? ctx.eventsByMissionId[missionId] ?? [] : [];

  const loading =
    Boolean(missionId?.trim()) && !mission && events.length === 0 && ctx.missionsLoading;

  return { mission, events, loading, error };
}

export function useMission(id: string): {
  mission: Mission | null;
  events: MissionEvent[];
  loading: boolean;
  error: string | null;
} {
  const ctx = useControlPlaneLive();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id.trim()) {
      setError(null);
      return;
    }
    let cancelled = false;
    setError(null);
    void (async () => {
      try {
        await ctx.bootstrapMission(id);
      } catch (e: unknown) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, ctx.bootstrapMission]);

  useEffect(() => {
    if (!id.trim() || ctx.streamConnected) return;
    const handle = window.setInterval(() => void ctx.bootstrapMission(id), 10000);
    return () => clearInterval(handle);
  }, [id, ctx.streamConnected, ctx.bootstrapMission]);

  const mission = id ? ctx.missionById[id] ?? ctx.missions.find((m) => m.id === id) ?? null : null;
  const events = id ? ctx.eventsByMissionId[id] ?? [] : [];

  const loading = Boolean(id.trim()) && !mission && events.length === 0;

  return { mission, events, loading, error };
}
