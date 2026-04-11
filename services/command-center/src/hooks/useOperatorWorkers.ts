import { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api";
import type { OperatorWorkersResponse } from "../lib/types";

export function useOperatorWorkers(pollIntervalMs = 30000): {
  data: OperatorWorkersResponse | null;
  error: string | null;
  loading: boolean;
  refetch: () => Promise<void>;
} {
  const [data, setData] = useState<OperatorWorkersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    try {
      const d = await api.getOperatorWorkers();
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
    return () => window.clearInterval(id);
  }, [refetch, pollIntervalMs]);

  return { data, error, loading, refetch };
}
