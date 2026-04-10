import { MissionCard } from "./MissionCard";
import type { Mission } from "../../lib/types";

export function MissionList({ missions }: { missions: Mission[] }) {
  return (
    <div className="flex flex-col gap-3">
      {missions.map((m) => (
        <MissionCard key={m.id} mission={m} />
      ))}
    </div>
  );
}
