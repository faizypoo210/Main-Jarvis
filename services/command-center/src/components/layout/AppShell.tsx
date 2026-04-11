import { useMemo, useState } from "react";
import { Outlet, useOutletContext } from "react-router-dom";
import { useControlPlaneLive, useMissions, usePendingApprovals } from "../../hooks/useControlPlane";
import { VoiceMode } from "../voice/VoiceMode";
import { CenterPane } from "./CenterPane";
import { LeftRail } from "./LeftRail";
import { MobileBottomNav } from "./MobileBottomNav";
import { RightPanel } from "./RightPanel";

export type ShellOutletContext = {
  openVoiceMode: () => void;
  /**
   * Single shell focus mission: conversation pipeline, `/missions/:id` detail, and right panel
   * all read this id so the inspector stays aligned with what the operator opened.
   */
  threadMissionId: string | null;
  setThreadMissionId: (id: string | null) => void;
};

export function useShellOutlet() {
  return useOutletContext<ShellOutletContext>();
}

export function AppShell() {
  const live = useControlPlaneLive();
  const { missions: panelMissions, loading: missionsLoading } = useMissions({ limit: 100 });
  const { missions: activeMissions } = useMissions({ status: "active", limit: 500 });
  const { approvals } = usePendingApprovals();

  const missionActiveCount = useMemo(() => activeMissions.length, [activeMissions]);
  const pendingApprovalCount = approvals.length;

  const [voiceOpen, setVoiceOpen] = useState(false);
  const [rightSheetOpen, setRightSheetOpen] = useState(false);
  const [threadMissionId, setThreadMissionId] = useState<string | null>(null);

  const outletCtx: ShellOutletContext = {
    openVoiceMode: () => setVoiceOpen(true),
    threadMissionId,
    setThreadMissionId,
  };

  return (
    <div className="flex h-[100dvh] flex-col overflow-hidden bg-[var(--bg-void)] md:flex-row">
      <LeftRail
        missionActiveCount={missionActiveCount}
        pendingApprovalCount={pendingApprovalCount}
        streamPhase={live.streamPhase}
      />

      <div className="flex min-h-0 min-w-0 flex-1 flex-col md:flex-row">
        <CenterPane
          onToggleRightPanel={() => setRightSheetOpen((o) => !o)}
          showRightToggle
        >
          <Outlet context={outletCtx} />
        </CenterPane>

        {/* Desktop right panel */}
        <div className="hidden min-h-0 lg:block">
          <RightPanel missions={panelMissions} missionsLoading={missionsLoading} threadMissionId={threadMissionId} />
        </div>
      </div>

      <MobileBottomNav />

      {/* Tablet / mobile overlay for right panel */}
      {rightSheetOpen ? (
        <div
          className="fixed inset-0 z-50 flex justify-end bg-black/60 lg:hidden"
          role="presentation"
          onClick={() => setRightSheetOpen(false)}
        >
          <div
            className="h-full w-[min(100vw,320px)] shadow-2xl animate-[fade-up_250ms_ease_forwards]"
            onClick={(e) => e.stopPropagation()}
          >
            <RightPanel
              missions={panelMissions}
              missionsLoading={missionsLoading}
              threadMissionId={threadMissionId}
              onClose={() => setRightSheetOpen(false)}
            />
          </div>
        </div>
      ) : null}

      <VoiceMode
        open={voiceOpen}
        onClose={() => setVoiceOpen(false)}
        threadMissionId={threadMissionId}
        activeMissionCount={missionActiveCount}
        liveStreamError={live.streamError}
        streamPhase={live.streamPhase}
      />
    </div>
  );
}
