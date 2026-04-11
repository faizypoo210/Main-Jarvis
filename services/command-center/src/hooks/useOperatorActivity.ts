import { useCallback, useEffect, useRef, useState } from "react";
import { useControlPlaneLive } from "../contexts/ControlPlaneLiveContext";
import * as api from "../lib/api";
import type { ActivityFeedCategory } from "../lib/types";
import type { ActivityFilterTab } from "../lib/activityPresentation";
import { mapActivityFilterToQuery } from "../lib/activityPresentation";
import type { ActivitySummary, OperatorActivityItem } from "../lib/types";

export function useOperatorActivity(filterTab: ActivityFilterTab): {
  summary: ActivitySummary | null;
  items: OperatorActivityItem[];
  nextBefore: string | null;
  error: string | null;
  loading: boolean;
  loadingMore: boolean;
  refresh: () => Promise<void>;
  loadMore: () => Promise<void>;
} {
  const ctx = useControlPlaneLive();
  const category: ActivityFeedCategory | undefined = mapActivityFilterToQuery(filterTab);

  const [summary, setSummary] = useState<ActivitySummary | null>(null);
  const [items, setItems] = useState<OperatorActivityItem[]>([]);
  const [nextBefore, setNextBefore] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const r = await api.getOperatorActivity({ limit: 50, category });
      setSummary(r.summary);
      setItems(r.items);
      setNextBefore(r.next_before);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setSummary(null);
      setItems([]);
      setNextBefore(null);
    } finally {
      setLoading(false);
    }
  }, [category]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const id = window.setInterval(() => void refresh(), 25000);
    return () => clearInterval(id);
  }, [refresh]);

  const revRef = useRef<number | null>(null);
  useEffect(() => {
    if (revRef.current === null) {
      revRef.current = ctx.eventStreamRevision;
      return;
    }
    if (ctx.eventStreamRevision === revRef.current) return;
    revRef.current = ctx.eventStreamRevision;
    const t = window.setTimeout(() => void refresh(), 1500);
    return () => clearTimeout(t);
  }, [ctx.eventStreamRevision, refresh]);

  const loadMore = useCallback(async () => {
    if (!nextBefore) return;
    try {
      setLoadingMore(true);
      const r = await api.getOperatorActivity({
        limit: 50,
        before: nextBefore,
        category,
      });
      setItems((prev) => [...prev, ...r.items]);
      setNextBefore(r.next_before);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingMore(false);
    }
  }, [nextBefore, category]);

  return {
    summary,
    items,
    nextBefore,
    error,
    loading,
    loadingMore,
    refresh,
    loadMore,
  };
}
