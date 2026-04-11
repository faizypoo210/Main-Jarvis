import { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api";
import type { HeartbeatOperatorResponse } from "../lib/types";

export function useOperatorHeartbeat(pollIntervalMs = 60000): {
  data: HeartbeatOperatorResponse | null;
  error: string | null;
  loading: boolean;
  refetch: () => Promise<void>;
} {
  const [data, setData] = useState<HeartbeatOperatorResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    try {
      const d = await api.getOperatorHeartbeat();
      setData(d);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refetch();
    const id = window.setInterval(() => void refetch(), pollIntervalMs);
    return () => clearInterval(id);
  }, [refetch, pollIntervalMs]);

  return { data, error, loading, refetch };
}
