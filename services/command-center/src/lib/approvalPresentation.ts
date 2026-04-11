import { OPERATOR_PHASE_LABELS } from "./missionPhase";
import { operatorCopy } from "./operatorCopy";

/**
 * Calm one-line hint after a successful approval decision (presentation-only).
 * Approve: aligns with the typical next derived phase after governance clears.
 * Deny: short confirmation without inventing backend status.
 */
export function approvalPostDecisionLine(decision: "approved" | "denied"): string {
  return decision === "approved"
    ? OPERATOR_PHASE_LABELS.resumed_waiting_for_execution
    : operatorCopy.approvalDecisionRecordedShort;
}
