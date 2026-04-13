import { useCallback, useEffect, useMemo, useState } from "react";
import { Outlet, useLocation, useNavigate, useOutletContext } from "react-router-dom";
import * as api from "../../lib/api";
import { useControlPlaneLive, useMissions, usePendingApprovals } from "../../hooks/useControlPlane";
import { VoiceMode } from "../voice/VoiceMode";
import { CenterPane } from "./CenterPane";
import { LeftRail } from "./LeftRail";
import { MobileBottomNav } from "./MobileBottomNav";
import { QuickCommandPalette, useQuickCommandShortcuts } from "./QuickCommandPalette";
import { RightPanel } from "./RightPanel";

export type ShellOutletContext = {
  openVoiceMode: () => void;
  /**
   * Single shell focus mission: conversation pipeline, `/missions/:id` detail, and right panel
   * all read this id so the inspector stays aligned with what the operator opened.
   */
  threadMissionId: string | null;
  setThreadMissionId: (id: string | null) => void;
  /**
   * When set, Overview may show a one-time handoff cue after global quick command created this mission.
   * Cleared when focus moves to another mission or is cleared.
   */
  quickCommandHandoffMissionId: string | null;
};

export function useShellOutlet() {
  return useOutletContext<ShellOutletContext>();
}

export function AppShell() {
  const live = useControlPlaneLive();
  const navigate = useNavigate();
  const location = useLocation();
  const { missions: panelMissions, loading: missionsLoading } = useMissions({ limit: 100 });
  const { missions: activeMissions } = useMissions({ status: "active", limit: 500 });
  const { approvals } = usePendingApprovals();

  const missionActiveCount = useMemo(() => activeMissions.length, [activeMissions]);
  const pendingApprovalCount = approvals.length;

  const [voiceOpen, setVoiceOpen] = useState(false);
  const [rightSheetOpen, setRightSheetOpen] = useState(false);
  const [threadMissionId, setThreadMissionId] = useState<string | null>(null);
  const [quickCommandHandoffMissionId, setQuickCommandHandoffMissionId] = useState<string | null>(null);
  const [quickOpen, setQuickOpen] = useState(false);

  const openQuickCommand = useCallback(() => setQuickOpen(true), []);
  const closeQuickCommand = useCallback(() => setQuickOpen(false), []);
  useQuickCommandShortcuts(quickOpen, openQuickCommand, closeQuickCommand);

  const quickShortcutLabel = useMemo(
    () =>
      typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/i.test(navigator.userAgent)
        ? "⌘K"
        : "Ctrl+K",
    []
  );

  const handleQuickCommandSubmit = useCallback(
    async (text: string) => {
      const res = await api.createCommand(text, "command_center");
      const mid = String(res.mission_id);
      setThreadMissionId(mid);
      setQuickCommandHandoffMissionId(mid);
      await live.bootstrapMission(mid);
      setQuickOpen(false);
      if (location.pathname !== "/") {
        navigate("/");
      }
    },
    [live, location.pathname, navigate]
  );

  useEffect(() => {
    if (quickCommandHandoffMissionId == null) return;
    if (threadMissionId == null || threadMissionId !== quickCommandHandoffMissionId) {
      setQuickCommandHandoffMissionId(null);
    }
  }, [threadMissionId, quickCommandHandoffMissionId]);

  const outletCtx: ShellOutletContext = {
    openVoiceMode: () => setVoiceOpen(true),
    threadMissionId,
    setThreadMissionId,
    quickCommandHandoffMissionId,
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
          onOpenQuickCommand={openQuickCommand}
          quickCommandShortcutLabel={quickShortcutLabel}
        >
          <Outlet context={outletCtx} />
        </CenterPane>

        {/* Desktop right panel */}
        <div className="hidden min-h-0 lg:block">
          <RightPanel
            missions={panelMissions}
            missionsLoading={missionsLoading}
            threadMissionId={threadMissionId}
            setThreadMissionId={setThreadMissionId}
          />
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
              setThreadMissionId={setThreadMissionId}
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

      <QuickCommandPalette
        open={quickOpen}
        onClose={() => setQuickOpen(false)}
        onSubmit={handleQuickCommandSubmit}
      />
    </div>
  );
}
