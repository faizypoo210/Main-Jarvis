import type { CSSProperties } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useShellOutlet } from "../layout/AppShell";
import * as api from "../../lib/api";
import { useControlPlaneLive } from "../../hooks/useControlPlane";
import type { Approval, Mission, MissionEvent } from "../../lib/types";
import { operatorCopy } from "../../lib/operatorCopy";
import { AgentActivity } from "./AgentActivity";
import { Composer } from "./Composer";
import { InlineApprovalCard } from "./InlineApprovalCard";
import { MessageBubble } from "./MessageBubble";
import { UserMessage } from "./UserMessage";

type ThreadItem =
  | { id: string; kind: "user"; body: string }
  | { id: string; kind: "activity"; text: string }
  | { id: string; kind: "status"; text: string }
  | {
      id: string;
      kind: "jarvis";
      body: string;
      time: string;
      routing?: string;
      missionIdTag?: string;
    }
  | { id: string; kind: "approval"; approval: Approval; missionId: string };

const stagger = (i: number): CSSProperties => ({
  animationDelay: `${i * 50}ms`,
});

const POLL_MS = 2000;
const MAX_TICKS = 90;

function StatusLine({ text }: { text: string }) {
  return (
    <div className="ml-9 py-1">
      <p className="text-xs text-[var(--text-muted)]">{text}</p>
    </div>
  );
}

function sortEventsAsc(events: MissionEvent[]): MissionEvent[] {
  return [...events].sort((a, b) => a.created_at.localeCompare(b.created_at));
}

/** Build a minimal Approval from enriched approval_requested mission event payload (control plane). */
function approvalFromRequestedEvent(ev: MissionEvent): Approval | null {
  const p = ev.payload;
  if (!p || typeof p !== "object") return null;
  const pid = (p as Record<string, unknown>).approval_id;
  if (typeof pid !== "string") return null;
  const missionId =
    typeof (p as Record<string, unknown>).mission_id === "string"
      ? ((p as Record<string, unknown>).mission_id as string)
      : ev.mission_id;
  const pr = p as Record<string, unknown>;
  return {
    id: pid,
    mission_id: missionId,
    action_type: typeof pr.action_type === "string" ? pr.action_type : "Action",
    risk_class: typeof pr.risk_class === "string" ? pr.risk_class : "amber",
    reason: typeof pr.reason === "string" ? pr.reason : null,
    command_text: null,
    dashclaw_decision_id: null,
    status: typeof pr.status === "string" ? pr.status : "pending",
    requested_by: typeof pr.requested_by === "string" ? pr.requested_by : "system",
    requested_via: typeof pr.requested_via === "string" ? pr.requested_via : "control_plane",
    decided_by: null,
    decided_via: null,
    decision_notes: null,
    created_at: ev.created_at,
    decided_at: null,
    expires_at: null,
  };
}

export function ConversationThread({ onVoiceClick }: { onVoiceClick: () => void }) {
  const { setThreadMissionId } = useShellOutlet();
  const live = useControlPlaneLive();
  const liveRef = useRef(live);
  liveRef.current = live;

  const [items, setItems] = useState<ThreadItem[]>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [resolveErrorId, setResolveErrorId] = useState<string | null>(null);

  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const watchedMissionIdsRef = useRef<Set<string>>(new Set());
  const processedEventIdsRef = useRef<Set<string>>(new Set());
  const terminalShownRef = useRef<Map<string, Set<string>>>(new Map());
  const tickCountsRef = useRef<Record<string, number>>({});

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  const stopPoll = useCallback((missionId: string) => {
    delete tickCountsRef.current[missionId];
  }, []);

  const resolveApproval = useCallback(
    async (approvalId: string, missionId: string, decision: "approved" | "denied") => {
      setResolvingId(approvalId);
      setResolveErrorId(null);
      try {
        await api.resolveApproval(approvalId, {
          decision,
          decided_by: "operator",
          decided_via: "command_center",
        });
        const decidedAt = new Date().toISOString();
        setItems((prev) =>
          prev.map((i) => {
            if (i.kind !== "approval" || i.missionId !== missionId || i.approval.id !== approvalId) {
              return i;
            }
            return {
              ...i,
              approval: {
                ...i.approval,
                status: decision,
                decided_at: decidedAt,
                decided_by: "operator",
                decided_via: "command_center",
              },
            };
          })
        );
        void liveRef.current.refetchPendingApprovals();
      } catch {
        setResolveErrorId(approvalId);
      } finally {
        setResolvingId(null);
      }
    },
    []
  );

  const processMissionTick = useCallback(
    async (missionId: string) => {
      tickCountsRef.current[missionId] = (tickCountsRef.current[missionId] ?? 0) + 1;
      if ((tickCountsRef.current[missionId] ?? 0) > MAX_TICKS) {
        stopPoll(missionId);
        return;
      }

      const l = liveRef.current;
      let mission: Mission;
      let events: MissionEvent[];
      let pending: Approval[];

      if (l.streamConnected) {
        let m = l.missionById[missionId];
        events = l.eventsByMissionId[missionId] ?? [];
        if (events.length === 0) {
          await l.bootstrapMission(missionId);
          events = liveRef.current.eventsByMissionId[missionId] ?? [];
        }
        if (!m) {
          try {
            m = await api.getMission(missionId);
          } catch {
            return;
          }
        }
        mission = m;
        pending = l.pendingApprovals.filter((a) => a.mission_id === missionId);
      } else {
        try {
          ;[mission, events, pending] = await Promise.all([
            api.getMission(missionId),
            api.getMissionEvents(missionId),
            api.getPendingApprovals(),
          ]);
          pending = pending.filter((a) => a.mission_id === missionId);
        } catch {
          return;
        }
      }

      const sorted = sortEventsAsc(events);
      let shouldStop = false;

      for (const ev of sorted) {
        if (processedEventIdsRef.current.has(ev.id)) continue;

        if (ev.event_type === "created") {
          processedEventIdsRef.current.add(ev.id);
          setItems((prev) => {
            if (prev.some((x) => x.id === `mission-created-${missionId}`)) return prev;
            return [
              ...prev,
              {
                id: `mission-created-${missionId}`,
                kind: "status",
                text: "Mission logged.",
              },
            ];
          });
          continue;
        }

        if (ev.event_type === "approval_requested") {
          processedEventIdsRef.current.add(ev.id);
          const fromApi = pending.find((a) => a.mission_id === missionId && a.status === "pending");
          const ap = fromApi ?? approvalFromRequestedEvent(ev);
          setItems((prev) => {
            if (prev.some((i) => i.kind === "approval" && i.missionId === missionId)) {
              return prev;
            }
            if (ap) {
              return [
                ...prev,
                {
                  id: `approval-${ap.id}`,
                  kind: "approval",
                  approval: ap,
                  missionId,
                },
              ];
            }
            return [
              ...prev,
              {
                id: `status-await-${ev.id}`,
                kind: "status",
                text: "Awaiting approval.",
              },
            ];
          });
          continue;
        }

        if (ev.event_type === "approval_resolved") {
          processedEventIdsRef.current.add(ev.id);
          const payload = ev.payload as Record<string, unknown> | null;
          const decisionRaw = typeof payload?.decision === "string" ? payload.decision : "";
          const aid = typeof payload?.approval_id === "string" ? payload.approval_id : null;
          const decidedAt =
            payload && typeof payload.decided_at === "string" ? payload.decided_at : new Date().toISOString();
          const statusNorm =
            decisionRaw === "approved" ? "approved" : decisionRaw === "denied" ? "denied" : decisionRaw;
          setItems((prev) => {
            const hadCard = prev.some(
              (i) =>
                i.kind === "approval" &&
                i.missionId === missionId &&
                (!aid || i.approval.id === aid)
            );
            const next = prev.map((i) => {
              if (i.kind !== "approval" || i.missionId !== missionId) return i;
              if (aid && i.approval.id !== aid) return i;
              return {
                ...i,
                approval: {
                  ...i.approval,
                  status: statusNorm || i.approval.status,
                  decided_at: decidedAt,
                  decided_by:
                    payload && typeof payload.decided_by === "string" ? payload.decided_by : i.approval.decided_by,
                  decided_via:
                    payload && typeof payload.decided_via === "string" ? payload.decided_via : i.approval.decided_via,
                },
              };
            });
            if (hadCard) return next;
            const line =
              decisionRaw === "approved"
                ? operatorCopy.approvalExecutionResumed
                : decisionRaw === "denied"
                  ? operatorCopy.approvalDeniedBlocked
                  : operatorCopy.approvalDecisionRecorded;
            return [...next, { id: `status-ar-${ev.id}`, kind: "status", text: line }];
          });
          continue;
        }

        if (ev.event_type === "receipt_recorded") {
          processedEventIdsRef.current.add(ev.id);
          const payload = ev.payload as Record<string, unknown> | null;
          const rawSummary = payload && typeof payload.summary === "string" ? payload.summary : "";
          const summary = rawSummary.trim();
          const missionFailed = mission.status === "failed";
          if (summary.length > 0) {
            setItems((prev) => {
              const exists = prev.some((x) => x.kind === "jarvis" && x.id === `exec-${ev.id}`);
              if (exists) return prev;
              return [
                ...prev,
                {
                  id: `exec-${ev.id}`,
                  kind: "jarvis",
                  body: summary,
                  time: new Date().toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  }),
                  missionIdTag: missionId,
                },
              ];
            });
          } else {
            setItems((prev) => {
              if (prev.some((x) => x.id === `status-receipt-${ev.id}`)) return prev;
              const text = missionFailed
                ? operatorCopy.receiptNoSummaryFailed
                : operatorCopy.receiptNoSummary;
              return [
                ...prev,
                {
                  id: `status-receipt-${ev.id}`,
                  kind: "status",
                  text,
                },
              ];
            });
          }
          shouldStop = true;
          const term = terminalShownRef.current.get(missionId) ?? new Set<string>();
          term.add("complete");
          terminalShownRef.current.set(missionId, term);
          continue;
        }

        processedEventIdsRef.current.add(ev.id);
      }

      const termSet = terminalShownRef.current.get(missionId) ?? new Set<string>();

      if (mission.status === "awaiting_approval") {
        const ap = liveRef.current.pendingApprovals.find(
          (a) => a.mission_id === missionId && a.status === "pending"
        );
        if (ap) {
          setItems((prev) => {
            if (prev.some((i) => i.kind === "approval" && i.missionId === missionId)) {
              return prev;
            }
            return [
              ...prev,
              { id: `approval-${ap.id}`, kind: "approval", approval: ap, missionId },
            ];
          });
        }
      }

      if (mission.status === "failed" && !termSet.has("failed")) {
        const hasReceipt = sorted.some(
          (e) =>
            e.event_type === "receipt_recorded" &&
            processedEventIdsRef.current.has(e.id)
        );
        if (!hasReceipt) {
          termSet.add("failed");
          terminalShownRef.current.set(missionId, termSet);
          setItems((prev) => {
            if (prev.some((x) => x.id === `status-fail-${missionId}`)) return prev;
            return [
              ...prev,
              {
                id: `status-fail-${missionId}`,
                kind: "status",
                text: operatorCopy.missionFailedNoReceiptDetail,
              },
            ];
          });
          shouldStop = true;
        }
      }

      if (mission.status === "blocked" && !termSet.has("blocked")) {
        termSet.add("blocked");
        terminalShownRef.current.set(missionId, termSet);
        setItems((prev) => {
          if (prev.some((x) => x.id === `blocked-${missionId}`)) return prev;
          return [
            ...prev,
            {
              id: `blocked-${missionId}`,
              kind: "status",
              text: "Mission blocked.",
            },
          ];
        });
        shouldStop = true;
      }

      if (mission.status === "complete" && !termSet.has("complete")) {
        const hasReceipt = sorted.some((e) => e.event_type === "receipt_recorded");
        if (!hasReceipt) {
          termSet.add("complete");
          terminalShownRef.current.set(missionId, termSet);
          setItems((prev) => {
            if (prev.some((x) => x.kind === "status" && x.id.startsWith(`status-done-${missionId}`))) {
              return prev;
            }
            return [
              ...prev,
              {
                id: `status-done-${missionId}`,
                kind: "status",
                text: "Mission complete.",
              },
            ];
          });
        } else {
          termSet.add("complete");
          terminalShownRef.current.set(missionId, termSet);
        }
        shouldStop = true;
      }

      if (shouldStop) {
        stopPoll(missionId);
      }
    },
    [stopPoll]
  );

  useEffect(() => {
    if (!live.streamConnected) return;
    for (const mid of watchedMissionIdsRef.current) {
      void processMissionTick(mid);
    }
  }, [
    live.streamConnected,
    live.eventStreamRevision,
    live.pendingApprovals,
    live.missionById,
    live.eventsByMissionId,
    processMissionTick,
  ]);

  useEffect(() => {
    if (live.streamConnected) return;
    const id = window.setInterval(() => {
      for (const mid of watchedMissionIdsRef.current) {
        void processMissionTick(mid);
      }
    }, POLL_MS);
    return () => clearInterval(id);
  }, [live.streamConnected, processMissionTick]);

  const startMissionPipeline = useCallback(
    (missionId: string) => {
      setThreadMissionId(missionId);
      watchedMissionIdsRef.current.add(missionId);
      void liveRef.current.bootstrapMission(missionId);
      void processMissionTick(missionId);
    },
    [processMissionTick, setThreadMissionId]
  );

  const handleSubmit = useCallback(
    async (text: string) => {
      setSubmitError(null);
      setSubmitting(true);
      try {
        const res = await api.createCommand(text, "command_center");
        const uid = crypto.randomUUID();
        const activityId = `activity-${uid}`;
        setItems((prev) => [
          ...prev,
          { id: `u-${uid}`, kind: "user", body: text },
          { id: activityId, kind: "activity", text: "Processing your request..." },
        ]);
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        timeoutRef.current = setTimeout(() => {
          timeoutRef.current = null;
          const mid = res.mission_id;
          setItems((prev) => {
            const without = prev.filter((x) => x.id !== activityId);
            return [
              ...without,
              {
                id: `j-${uid}`,
                kind: "jarvis",
                body: "Understood. I'm on it — I'll keep this thread updated.",
                time: new Date().toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                }),
                missionIdTag: mid,
              },
            ];
          });
          startMissionPipeline(mid);
        }, 1200);
      } catch {
        setSubmitError("Could not reach Jarvis — try again");
      } finally {
        setSubmitting(false);
      }
    },
    [startMissionPipeline]
  );

  const streamPhase = live.streamPhase;

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-4 md:px-6">
        <div className="mx-auto flex max-w-3xl flex-col gap-4 pb-4">
          {streamPhase !== "live" ? (
            <div
              className="rounded-lg border border-[var(--bg-border)] bg-[var(--bg-void)]/50 px-3 py-2 text-[10px] leading-snug text-[var(--text-muted)]"
              role="status"
            >
              {streamPhase === "reconnecting"
                ? operatorCopy.liveReconnecting
                : operatorCopy.liveOfflinePolling}
            </div>
          ) : null}
          {items.map((item, index) => {
            if (item.kind === "user") {
              return (
                <div key={item.id}>
                  <UserMessage body={item.body} />
                </div>
              );
            }
            if (item.kind === "activity") {
              return (
                <div key={item.id}>
                  <AgentActivity text={item.text} />
                </div>
              );
            }
            if (item.kind === "status") {
              return (
                <div key={item.id}>
                  <StatusLine text={item.text} />
                </div>
              );
            }
            if (item.kind === "approval") {
              return (
                <div key={item.id} className="flex justify-start">
                  <InlineApprovalCard
                    approval={item.approval}
                    missionId={item.missionId}
                    resolving={resolvingId === item.approval.id}
                    resolveError={resolveErrorId === item.approval.id ? "err" : null}
                    onApprove={() => void resolveApproval(item.approval.id, item.missionId, "approved")}
                    onDeny={() => void resolveApproval(item.approval.id, item.missionId, "denied")}
                  />
                </div>
              );
            }
            const delay = index < 5 ? stagger(index) : undefined;
            return (
              <div
                key={item.id}
                className={
                  index < 5
                    ? "animate-[fade-up_250ms_ease_forwards] opacity-0 [animation-fill-mode:forwards]"
                    : undefined
                }
                style={delay}
              >
                <MessageBubble
                  body={item.body}
                  time={item.time}
                  routing={item.routing}
                  missionIdTag={item.missionIdTag}
                />
              </div>
            );
          })}
        </div>
      </div>
      <div className="pb-[env(safe-area-inset-bottom,0px)]">
        <Composer
          onVoiceClick={onVoiceClick}
          onSubmit={handleSubmit}
          submitError={submitError}
          submitting={submitting}
        />
      </div>
    </div>
  );
}
