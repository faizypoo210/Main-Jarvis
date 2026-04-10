import { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api";
import type { Approval, Mission, MissionEvent } from "../lib/types";

export function useMissions(params?: {
  status?: string;
  limit?: number;
}): {
  missions: Mission[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
} {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (isPoll: boolean) => {
      if (!isPoll) {
        setLoading(true);
      }
      try {
        const data = await api.getMissions({
          status: params?.status,
          limit: params?.limit ?? 500,
        });
        setMissions(data);
        setError(null);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
        if (!isPoll) {
          setMissions([]);
        }
      } finally {
        if (!isPoll) {
          setLoading(false);
        }
      }
    },
    [params?.status, params?.limit]
  );

  useEffect(() => {
    void load(false);
    const id = window.setInterval(() => void load(true), 5000);
    return () => clearInterval(id);
  }, [load]);

  const refetch = useCallback(async () => {
    await load(false);
  }, [load]);

  return { missions, loading, error, refetch };
}

export function usePendingApprovals(): {
  approvals: Approval[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
} {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (isPoll: boolean) => {
    if (!isPoll) {
      setLoading(true);
    }
    try {
      const data = await api.getPendingApprovals();
      setApprovals(data);
      setError(null);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      if (!isPoll) {
        setApprovals([]);
      }
    } finally {
      if (!isPoll) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void load(false);
    const id = window.setInterval(() => void load(true), 3000);
    return () => clearInterval(id);
  }, [load]);

  const refetch = useCallback(async () => {
    await load(false);
  }, [load]);

  return { approvals, loading, error, refetch };
}

export function useMission(id: string): {
  mission: Mission | null;
  events: MissionEvent[];
  loading: boolean;
  error: string | null;
} {
  const [mission, setMission] = useState<Mission | null>(null);
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id.trim()) {
      setMission(null);
      setEvents([]);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([api.getMission(id), api.getMissionEvents(id)])
      .then(([m, ev]) => {
        if (!cancelled) {
          setMission(m);
          setEvents(ev);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setMission(null);
          setEvents([]);
          setError(e instanceof Error ? e.message : String(e));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [id]);

  return { mission, events, loading, error };
}
