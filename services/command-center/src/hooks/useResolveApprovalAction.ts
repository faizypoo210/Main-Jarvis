import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "../lib/api";
import { useControlPlaneLive } from "../contexts/ControlPlaneLiveContext";

export type LastResolvedApproval = {
  id: string;
  decision: "approved" | "denied";
};

export type ResolveApprovalSuccessOptions = {
  /**
   * Runs after a successful API response, before shared refetches.
   * Use for local UI (e.g. thread items, mission bundle) that should update immediately.
   */
  onSuccess?: () => void | Promise<void>;
};

/**
 * Shared client-side approval resolution: one mutation path, duplicate-submit guard,
 * quiet error surface, consistent post-success refresh (pending list + missions),
 * and ephemeral success signal after the API succeeds (not speculative).
 */
export function useResolveApprovalAction() {
  const live = useControlPlaneLive();
  const [resolvingApprovalId, setResolvingApprovalId] = useState<string | null>(null);
  const [resolveErrorApprovalId, setResolveErrorApprovalId] = useState<string | null>(null);
  const [lastResolved, setLastResolved] = useState<LastResolvedApproval | null>(null);
  const inFlightRef = useRef(false);

  const clearResolveError = useCallback(() => setResolveErrorApprovalId(null), []);
  const clearResolvedState = useCallback(() => setLastResolved(null), []);

  /** Clear ephemeral success once server pending list no longer has this approval as pending. */
  useEffect(() => {
    if (!lastResolved) return;
    const stillPending = live.pendingApprovals.some(
      (a) => a.id === lastResolved.id && a.status === "pending"
    );
    if (!stillPending) {
      const t = window.setTimeout(() => setLastResolved(null), 2000);
      return () => window.clearTimeout(t);
    }
  }, [live.pendingApprovals, lastResolved]);

  const resolve = useCallback(
    async (
      approvalId: string,
      decision: "approved" | "denied",
      opts?: ResolveApprovalSuccessOptions
    ) => {
      if (!approvalId.trim()) return;
      if (inFlightRef.current) return;

      setLastResolved(null);
      inFlightRef.current = true;
      setResolvingApprovalId(approvalId);
      setResolveErrorApprovalId(null);
      try {
        await api.resolveApproval(approvalId, {
          decision,
          decided_by: "operator",
          decided_via: "command_center",
        });
        setLastResolved({ id: approvalId, decision });
        await opts?.onSuccess?.();
        await live.refetchPendingApprovals();
        await live.refetchMissions();
      } catch {
        setResolveErrorApprovalId(approvalId);
        setLastResolved(null);
      } finally {
        inFlightRef.current = false;
        setResolvingApprovalId(null);
      }
    },
    [live]
  );

  /** For race UI: success hint only when not actively resolving this id. */
  const recentlyResolvedDecisionFor = useCallback(
    (approvalId: string): "approved" | "denied" | null => {
      if (resolvingApprovalId === approvalId) return null;
      if (lastResolved?.id !== approvalId) return null;
      return lastResolved.decision;
    },
    [lastResolved, resolvingApprovalId]
  );

  return {
    resolve,
    resolvingApprovalId,
    resolveErrorApprovalId,
    clearResolveError,
    lastResolved,
    clearResolvedState,
    recentlyResolvedDecisionFor,
  };
}
