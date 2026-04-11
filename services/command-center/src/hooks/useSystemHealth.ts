import { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api";
import type { SystemHealthResponse } from "../lib/types";

export function useSystemHealth(pollIntervalMs = 30000): {
  data: SystemHealthResponse | null;
  error: string | null;
  loading: boolean;
  refetch: () => Promise<void>;
} {
  const [data, setData] = useState<SystemHealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    try {
      const d = await api.getSystemHealth();
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
