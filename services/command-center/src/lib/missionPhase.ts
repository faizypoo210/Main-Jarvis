import type { Approval, Mission, MissionEvent, Receipt } from "./types";
import { normalizeMissionStatus } from "./format";

/**
 * Presentation-only mission phase derived from mission row + timeline events + approvals + receipts.
 * Not a second source of truth — same inputs as the rest of Command Center.
 */
export type OperatorMissionPhase =
  | "awaiting_approval"
  | "resumed_waiting_for_execution"
  | "executing"
  | "execution_evidence_received"
  | "complete"
  | "failed"
  | "blocked";

export type OperatorMissionPhaseView = {
  phase: OperatorMissionPhase;
  /** Short, calm operator-facing line */
  label: string;
};

/** Single canonical operator-facing strings (thread, voice, detail, readouts). */
export const OPERATOR_PHASE_LABELS: Record<OperatorMissionPhase, string> = {
  awaiting_approval: "Awaiting approval",
  resumed_waiting_for_execution: "Approved - waiting for execution output",
  executing: "Executing",
  execution_evidence_received: "Execution updated",
  complete: "Complete",
  failed: "Failed",
  blocked: "Blocked",
};

function hasPendingApprovalForMission(mission: Mission, approvals: Approval[]): boolean {
  return approvals.some((a) => a.mission_id === mission.id && a.status === "pending");
}

/** True when timeline or bundle lists execution evidence (receipt). See also `missionLatestResult.ts` for compact “latest output” scan lines. */
export function hasExecutionEvidence(events: MissionEvent[], receipts: Receipt[] | null): boolean {
  if (events.some((e) => e.event_type === "receipt_recorded")) return true;
  return (receipts?.length ?? 0) > 0;
}

/** True when an approval_resolved event indicates approve (not deny). */
function hasApprovedResolutionInTimeline(events: MissionEvent[]): boolean {
  for (const e of events) {
    if (e.event_type !== "approval_resolved") continue;
    const p = e.payload as { decision?: string } | null;
    if (p?.decision === "denied") continue;
    return true;
  }
  return false;
}

/**
 * Derive operator phase from authoritative mission status, events, approvals, and receipts.
 * Complete/failed take precedence; active + receipt is never labeled "Complete".
 */
export function deriveOperatorMissionPhase(
  mission: Mission,
  events: MissionEvent[],
  approvals: Approval[],
  receipts: Receipt[] | null
): OperatorMissionPhaseView {
  const st = mission.status;
  const pending = hasPendingApprovalForMission(mission, approvals);
  const evidence = hasExecutionEvidence(events, receipts);
  const approvedResolution = hasApprovedResolutionInTimeline(events);

  if (st === "failed") {
    return { phase: "failed", label: OPERATOR_PHASE_LABELS.failed };
  }
  if (st === "complete") {
    return { phase: "complete", label: OPERATOR_PHASE_LABELS.complete };
  }
  if (st === "blocked") {
    return { phase: "blocked", label: OPERATOR_PHASE_LABELS.blocked };
  }

  if (pending) {
    return { phase: "awaiting_approval", label: OPERATOR_PHASE_LABELS.awaiting_approval };
  }
  if (st === "awaiting_approval" && !approvedResolution) {
    return { phase: "awaiting_approval", label: OPERATOR_PHASE_LABELS.awaiting_approval };
  }

  /** Stale mission row still "awaiting_approval" while timeline already has approve — match events. */
  if (st === "awaiting_approval" && approvedResolution) {
    if (evidence) {
      return {
        phase: "execution_evidence_received",
        label: OPERATOR_PHASE_LABELS.execution_evidence_received,
      };
    }
    return {
      phase: "resumed_waiting_for_execution",
      label: OPERATOR_PHASE_LABELS.resumed_waiting_for_execution,
    };
  }

  const norm = normalizeMissionStatus(st);

  if (norm === "active" || norm === "pending") {
    if (evidence) {
      return {
        phase: "execution_evidence_received",
        label: OPERATOR_PHASE_LABELS.execution_evidence_received,
      };
    }
    if (norm === "active") {
      if (approvedResolution) {
        return {
          phase: "resumed_waiting_for_execution",
          label: OPERATOR_PHASE_LABELS.resumed_waiting_for_execution,
        };
      }
      return { phase: "executing", label: OPERATOR_PHASE_LABELS.executing };
    }
    return { phase: "executing", label: OPERATOR_PHASE_LABELS.executing };
  }

  return {
    phase: "executing",
    label: st.replace(/_/g, " ").trim() || "In progress",
  };
}
