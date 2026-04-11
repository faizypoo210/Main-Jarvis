import { useCallback, useEffect, useRef, useState } from "react";
import { useControlPlaneLive } from "../contexts/ControlPlaneLiveContext";
import * as api from "../lib/api";
import type { InboxGroupTab, InboxStatusFilter, OperatorInboxResponse } from "../lib/types";

export function useOperatorInbox(
  group: InboxGroupTab,
  status: InboxStatusFilter
): {
  data: OperatorInboxResponse | null;
  error: string | null;
  loading: boolean;
  refresh: () => Promise<void>;
  acknowledge: (itemKey: string) => Promise<void>;
  snooze: (itemKey: string, minutes: number) => Promise<void>;
  dismiss: (itemKey: string) => Promise<void>;
} {
  const ctx = useControlPlaneLive();
  const [data, setData] = useState<OperatorInboxResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const r = await api.getOperatorInbox({
        group: group === "all" ? undefined : group,
        status,
        limit: 120,
      });
      setData(r);
      setError(null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [group, status]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const id = window.setInterval(() => void refresh(), 30000);
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

  const acknowledge = useCallback(
    async (itemKey: string) => {
      await api.postOperatorInboxAcknowledge(itemKey);
      await refresh();
    },
    [refresh]
  );

  const snooze = useCallback(
    async (itemKey: string, minutes: number) => {
      await api.postOperatorInboxSnooze(itemKey, minutes);
      await refresh();
    },
    [refresh]
  );

  const dismiss = useCallback(
    async (itemKey: string) => {
      await api.postOperatorInboxDismiss(itemKey);
      await refresh();
    },
    [refresh]
  );

  return { data, error, loading, refresh, acknowledge, snooze, dismiss };
}
