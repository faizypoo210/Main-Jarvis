import { useMemo } from "react";
import { MissionCard } from "./MissionCard";
import { useControlPlaneLive } from "../../hooks/useControlPlane";
import { sortMissionsForOperatorListing } from "../../lib/missionListPriority";
import type { Mission } from "../../lib/types";

export function MissionList({ missions }: { missions: Mission[] }) {
  const live = useControlPlaneLive();
  const sorted = useMemo(
    () => sortMissionsForOperatorListing(missions, live.eventsByMissionId, live.pendingApprovals, null),
    [missions, live.eventsByMissionId, live.pendingApprovals]
  );

  return (
    <div className="flex flex-col gap-3">
      {sorted.map((m) => (
        <MissionCard key={m.id} mission={m} />
      ))}
    </div>
  );
}
