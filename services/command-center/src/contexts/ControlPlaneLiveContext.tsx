import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import * as api from "../lib/api";
import type { Approval, Mission, MissionBundle, MissionEvent } from "../lib/types";

const MAX_BACKOFF_MS = 30_000;
const BASE_BACKOFF_MS = 1000;

function backoffDelayMs(attempt: number): number {
  return Math.min(MAX_BACKOFF_MS, BASE_BACKOFF_MS * Math.pow(2, attempt));
}

/** Single SSE subscription; reconnect uses new AbortController after prior cleanup. */
export type StreamPhase = "live" | "reconnecting" | "offline";

export type ControlPlaneLiveValue = {
  missions: Mission[];
  missionsLoading: boolean;
  missionsError: string | null;
  pendingApprovals: Approval[];
  pendingLoading: boolean;
  pendingError: string | null;
  /** Canonical timeline per mission (hydration + SSE append, deduped by event id). */
  eventsByMissionId: Record<string, MissionEvent[]>;
  missionById: Record<string, Mission | undefined>;
  /** True when SSE is connected (HTTP 200 stream open). */
  streamConnected: boolean;
  /** Last error string from the stream layer (not necessarily blocking reconnect). */
  streamError: string | null;
  /** Coarse UI state for live link health. */
  streamPhase: StreamPhase;
  /** Bumps when any live message is applied (for pipeline subscribers). */
  eventStreamRevision: number;
  refetchMissions: () => Promise<void>;
  refetchPendingApprovals: () => Promise<void>;
  bootstrapMission: (missionId: string) => Promise<void>;
  /** Merge bundle into shared state (mission list, events, missionById). */
  hydrateMissionBundle: (bundle: MissionBundle) => void;
};

const ControlPlaneLiveContext = createContext<ControlPlaneLiveValue | null>(null);

function mergeMissionList(prev: Mission[], m: Mission): Mission[] {
  const idx = prev.findIndex((x) => x.id === m.id);
  if (idx >= 0) {
    const next = [...prev];
    next[idx] = m;
    return next;
  }
  return [m, ...prev];
}

function appendEvent(
  prev: Record<string, MissionEvent[]>,
  e: MissionEvent
): Record<string, MissionEvent[]> {
  const mid = e.mission_id;
  const list = [...(prev[mid] ?? [])];
  if (list.some((x) => x.id === e.id)) {
    return prev;
  }
  list.push(e);
  list.sort((a, b) => {
    const t = a.created_at.localeCompare(b.created_at);
    if (t !== 0) return t;
    return a.id.localeCompare(b.id);
  });
  return { ...prev, [mid]: list };
}

/** Merge bundle fetch with live SSE state without dropping events (idempotent by event id). */
function mergeMissionEvents(existing: MissionEvent[], incoming: MissionEvent[]): MissionEvent[] {
  const map = new Map<string, MissionEvent>();
  for (const e of existing) map.set(e.id, e);
  for (const e of incoming) map.set(e.id, e);
  return [...map.values()].sort((a, b) => {
    const t = a.created_at.localeCompare(b.created_at);
    if (t !== 0) return t;
    return a.id.localeCompare(b.id);
  });
}

export function ControlPlaneLiveProvider({ children }: { children: ReactNode }) {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [missionsLoading, setMissionsLoading] = useState(true);
  const [missionsError, setMissionsError] = useState<string | null>(null);
  const [pendingApprovals, setPendingApprovals] = useState<Approval[]>([]);
  const [pendingLoading, setPendingLoading] = useState(true);
  const [pendingError, setPendingError] = useState<string | null>(null);
  const [eventsByMissionId, setEventsByMissionId] = useState<Record<string, MissionEvent[]>>({});
  const [missionById, setMissionById] = useState<Record<string, Mission | undefined>>({});
  const [streamPhase, setStreamPhase] = useState<StreamPhase>("reconnecting");
  const [streamError, setStreamError] = useState<string | null>(null);
  const [eventStreamRevision, setEventStreamRevision] = useState(0);

  const bump = useCallback(() => {
    setEventStreamRevision((r) => r + 1);
  }, []);

  const refetchMissions = useCallback(async () => {
    try {
      const data = await api.getMissions({ limit: 500 });
      setMissions(data);
      setMissionsError(null);
      setMissionById((prev) => {
        const next = { ...prev };
        for (const m of data) {
          next[m.id] = m;
        }
        return next;
      });
    } catch (e: unknown) {
      setMissionsError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const refetchPendingApprovals = useCallback(async () => {
    try {
      const data = await api.getPendingApprovals();
      setPendingApprovals(data);
      setPendingError(null);
    } catch (e: unknown) {
      setPendingError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const hydrateMissionBundle = useCallback((b: MissionBundle) => {
    setMissionById((prev) => ({ ...prev, [b.mission.id]: b.mission }));
    setMissions((prev) => mergeMissionList(prev, b.mission));
    setEventsByMissionId((prev) => {
      const prior = prev[b.mission.id] ?? [];
      const merged = mergeMissionEvents(prior, b.events);
      return { ...prev, [b.mission.id]: merged };
    });
  }, []);

  const bootstrapMission = useCallback(
    async (missionId: string) => {
      const id = missionId.trim();
      if (!id) return;
      try {
        const b = await api.getMissionBundle(id);
        hydrateMissionBundle(b);
      } catch {
        try {
          const [m, ev] = await Promise.all([api.getMission(id), api.getMissionEvents(id)]);
          setMissionById((prev) => ({ ...prev, [m.id]: m }));
          setMissions((prev) => mergeMissionList(prev, m));
          setEventsByMissionId((prev) => ({ ...prev, [id]: ev }));
        } catch {
          /* ignore */
        }
      }
    },
    [hydrateMissionBundle]
  );

  useEffect(() => {
    let cancelled = false;
    async function hydrate() {
      setMissionsLoading(true);
      setPendingLoading(true);
      try {
        const [m, a] = await Promise.all([
          api.getMissions({ limit: 500 }),
          api.getPendingApprovals(),
        ]);
        if (cancelled) return;
        setMissions(m);
        setPendingApprovals(a);
        const byId: Record<string, Mission> = {};
        for (const x of m) {
          byId[x.id] = x;
        }
        setMissionById(byId);
        setMissionsError(null);
        setPendingError(null);
      } catch (e: unknown) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : String(e);
          setMissionsError(msg);
          setPendingError(msg);
        }
      } finally {
        if (!cancelled) {
          setMissionsLoading(false);
          setPendingLoading(false);
        }
      }
    }
    void hydrate();
    return () => {
      cancelled = true;
    };
  }, []);

  const refetchPendingRef = useRef(refetchPendingApprovals);
  refetchPendingRef.current = refetchPendingApprovals;

  const applyLiveMessage = useCallback(
    (msg: api.LiveStreamMessage) => {
      bump();
      if (msg.type === "mission_event") {
        setEventsByMissionId((prev) => appendEvent(prev, msg.event));
        const et = msg.event.event_type;
        if (
          et === "approval_requested" ||
          et === "approval_resolved" ||
          et === "mission_status_changed"
        ) {
          void refetchPendingRef.current();
        }
      }
      if (msg.type === "mission") {
        const m = msg.mission;
        setMissionById((prev) => ({ ...prev, [m.id]: m }));
        setMissions((prev) => mergeMissionList(prev, m));
      }
    },
    [bump]
  );

  useEffect(() => {
    let cancelled = false;
    let attempt = 0;
    let backoffTimer: ReturnType<typeof setTimeout> | null = null;
    let ac: AbortController | null = null;

    const clearBackoff = () => {
      if (backoffTimer != null) {
        clearTimeout(backoffTimer);
        backoffTimer = null;
      }
    };

    const scheduleReconnect = (reason: string) => {
      if (cancelled) return;
      clearBackoff();
      setStreamPhase("reconnecting");
      setStreamError(reason);
      const delay = backoffDelayMs(attempt);
      attempt += 1;
      backoffTimer = window.setTimeout(() => {
        backoffTimer = null;
        if (cancelled) return;
        connect();
      }, delay);
    };

    const connect = () => {
      if (cancelled) return;
      clearBackoff();
      ac?.abort();
      ac = new AbortController();
      setStreamPhase("reconnecting");
      setStreamError(null);

      api.connectControlPlaneStream(
        (msg) => {
          if (cancelled) return;
          applyLiveMessage(msg);
        },
        (err) => {
          if (cancelled) return;
          if (ac?.signal.aborted) return;
          setStreamPhase("offline");
          setStreamError(err.message);
          scheduleReconnect(err.message);
        },
        ac.signal,
        {
          onOpen: () => {
            if (cancelled) return;
            attempt = 0;
            setStreamPhase("live");
            setStreamError(null);
          },
          onStreamEnd: () => {
            if (cancelled) return;
            if (ac?.signal.aborted) return;
            setStreamPhase("offline");
            scheduleReconnect("stream closed");
          },
        }
      );
    };

    connect();

    return () => {
      cancelled = true;
      clearBackoff();
      ac?.abort();
    };
  }, [applyLiveMessage]);

  const streamConnected = streamPhase === "live";

  const value = useMemo<ControlPlaneLiveValue>(
    () => ({
      missions,
      missionsLoading,
      missionsError,
      pendingApprovals,
      pendingLoading,
      pendingError,
      eventsByMissionId,
      missionById,
      streamConnected,
      streamError,
      streamPhase,
      eventStreamRevision,
      refetchMissions,
      refetchPendingApprovals,
      bootstrapMission,
      hydrateMissionBundle,
    }),
    [
      missions,
      missionsLoading,
      missionsError,
      pendingApprovals,
      pendingLoading,
      pendingError,
      eventsByMissionId,
      missionById,
      streamConnected,
      streamError,
      streamPhase,
      eventStreamRevision,
      refetchMissions,
      refetchPendingApprovals,
      bootstrapMission,
      hydrateMissionBundle,
    ]
  );

  return (
    <ControlPlaneLiveContext.Provider value={value}>{children}</ControlPlaneLiveContext.Provider>
  );
}

export function useControlPlaneLive(): ControlPlaneLiveValue {
  const ctx = useContext(ControlPlaneLiveContext);
  if (!ctx) {
    throw new Error("useControlPlaneLive must be used within ControlPlaneLiveProvider");
  }
  return ctx;
}
