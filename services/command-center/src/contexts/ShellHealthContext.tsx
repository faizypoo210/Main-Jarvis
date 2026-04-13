import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useControlPlaneLive } from "./ControlPlaneLiveContext";
import { useOperatorHeartbeat } from "../hooks/useOperatorHeartbeat";
import { useSystemHealth } from "../hooks/useSystemHealth";
import { deriveShellRuntimeSummary, type ShellRuntimeSummary } from "../lib/operatorRuntimeHealth";

type ShellHealthContextValue = {
  live: ReturnType<typeof useControlPlaneLive>;
  systemHealth: ReturnType<typeof useSystemHealth>;
  hb: ReturnType<typeof useOperatorHeartbeat>;
  summary: ShellRuntimeSummary;
};

const ShellHealthContext = createContext<ShellHealthContextValue | null>(null);

export function ShellHealthProvider({ children }: { children: ReactNode }) {
  const live = useControlPlaneLive();
  const systemHealth = useSystemHealth(30000);
  const hb = useOperatorHeartbeat(90000);

  const summary = useMemo(
    () =>
      deriveShellRuntimeSummary({
        streamPhase: live.streamPhase,
        streamError: live.streamError,
        systemHealthError: systemHealth.error,
        systemHealthLoading: systemHealth.loading,
        systemHealthData: systemHealth.data,
        heartbeatError: hb.error,
        heartbeatLoading: hb.loading,
        heartbeatOpenCount: hb.data?.open_count ?? null,
      }),
    [
      live.streamPhase,
      live.streamError,
      systemHealth.error,
      systemHealth.loading,
      systemHealth.data,
      hb.error,
      hb.loading,
      hb.data?.open_count,
    ]
  );

  const value = useMemo(
    () => ({ live, systemHealth, hb, summary }),
    [live, systemHealth, hb, summary]
  );

  return <ShellHealthContext.Provider value={value}>{children}</ShellHealthContext.Provider>;
}

export function useShellHealth(): ShellHealthContextValue {
  const ctx = useContext(ShellHealthContext);
  if (!ctx) {
    throw new Error("useShellHealth must be used within ShellHealthProvider");
  }
  return ctx;
}
