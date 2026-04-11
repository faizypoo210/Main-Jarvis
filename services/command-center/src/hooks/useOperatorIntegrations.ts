import { useCallback, useEffect, useState } from "react";
import * as api from "../lib/api";
import type { OperatorIntegrationsResponse } from "../lib/types";

export function useOperatorIntegrations(pollIntervalMs = 45000): {
  data: OperatorIntegrationsResponse | null;
  error: string | null;
  loading: boolean;
  refetch: () => Promise<void>;
} {
  const [data, setData] = useState<OperatorIntegrationsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    try {
      const r = await api.getOperatorIntegrations();
      setData(r);
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
  }, [refetch]);

  useEffect(() => {
    const id = window.setInterval(() => void refetch(), pollIntervalMs);
    return () => clearInterval(id);
  }, [refetch, pollIntervalMs]);

  return { data, error, loading, refetch };
}
